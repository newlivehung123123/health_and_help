#!/usr/bin/env python3
"""Build the data files that the Health & Help web app reads.

The build makes no API calls and costs nothing. It reads the checked candidate sites, the source check, the
province list with an approximate point for each provincial capital, and the taxonomy. It writes one JSON
file for the web app and one CSV for download. The public files exclude the model's notes, which can name
people, and the bookkeeping columns of the discovery runs. Pins on the map mark the provincial capital and
never the address of a service.

    python scripts/build_site_data.py    writes site/data/sites.json, site/data/health_and_help_candidates.csv and site/data/codebook.md
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover as d  # noqa: E402

CHECKED_CSV = d.ROOT / "data" / "candidates_checked.csv"
CHECK_CSV = d.ROOT / "data" / "source_check.csv"
PROVINCES_CSV = d.CONFIG / "provinces.csv"
POINTS_CSV = d.CONFIG / "province_points.csv"
TAXONOMY_JSON = d.CONFIG / "taxonomy.json"
COST_LOG = d.ROOT / "data" / "discovery" / "cost_log.csv"
CODEBOOK = d.ROOT / "codebook.md"
SITE_DATA = d.ROOT / "site" / "data"

NATIONWIDE = "nationwide"
BARE_MARK = "พนักงานบริการ without a qualifier"  # how check_sources.py reports the bare term
THAILAND = (5.5, 20.5, 97.3, 105.7)              # south, north, west, east, for a sanity check of the points
PUBLIC_FIELDS = ["org_id", "site_id", "name_en", "name_th", "acronym", "org_type", "level", "province_codes",
                 "province_en", "region", "city", "sex_worker_mention", "sex_worker_led", "services_mentioned",
                 "meets_inclusion", "website", "facebook_or_line", "other_urls", "partner_list_urls",
                 "evidence_urls", "evidence_quotes", "quotes_found", "sex_work_terms_on_pages", "pages_not_read",
                 "latest_activity_seen"]
PRIVATE_FIELDS = {"notes", "found_in_rounds", "job_ids", "n_records"}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split(value, sep="; "):
    return [v.strip() for v in (value or "").split(sep) if v.strip()]


def clean_quote(quote):
    """A quote as the page shows it, without the bold markers the model sometimes adds."""
    return re.sub(r"\s+", " ", quote.replace("**", "")).strip()


def load_provinces(provinces_csv=PROVINCES_CSV, points_csv=POINTS_CSV):
    points = {r["code"]: (float(r["lat"]), float(r["lon"])) for r in read_csv(points_csv)}
    provinces = []
    for r in read_csv(provinces_csv):
        if r["code"] not in points:
            raise ValueError(f"{points_csv} has no point for {r['code']} {r['name_en']}")
        lat, lon = points[r["code"]]
        south, north, west, east = THAILAND
        if not (south <= lat <= north and west <= lon <= east):
            raise ValueError(f"the point for {r['code']} {r['name_en']} lies outside Thailand")
        provinces.append({"code": r["code"], "name_en": r["name_en"], "name_th": r["name_th"],
                          "region": r["region"], "lat": lat, "lon": lon})
    return provinces


def search_spend(path=COST_LOG):
    """What the discovery runs spent on the API, in US dollars, and how many web searches they ran."""
    if not Path(path).exists():
        return 0.0, 0
    rows = read_csv(path)
    return round(sum(float(r["cost_usd"] or 0) for r in rows), 2), sum(int(r["web_searches"] or 0) for r in rows)


def site_status(row, core):
    """included when a source names sex workers and the site offers a core service, the codebook's rule."""
    if row["sex_worker_mention"] != "yes":
        return "unclear"
    return "included" if core & set(split(row["services_mentioned"])) else "unconfirmed"


def page_state(page):
    if page == "read":
        return "read"
    return "social" if page.startswith("social page") else "not read"


def evidence(row, checks):
    """Each evidence page of a site with its quote and the result of the source check.

    A check row belongs to the site when both its page and its quote are among the site's evidence."""
    urls, quotes = set(split(row["evidence_urls"])), set(split(row["evidence_quotes"], " | "))
    items, seen = [], set()
    for c in checks:
        quote = (c["evidence_quote"] or "").strip()
        if c["excluded"] or c["evidence_url"] not in urls or quote not in quotes or (c["evidence_url"], quote) in seen:
            continue
        seen.add((c["evidence_url"], quote))
        items.append({"url": c["evidence_url"], "quote": clean_quote(quote), "check": c["quote_check"],
                      "page": page_state(c["page"])})
    return items


def site_record(row, checks, core, service_order, region_of):
    codes = split(row["province_codes"])
    nationwide = codes == [NATIONWIDE]
    provinces = [] if nationwide else codes
    terms = split(row["sex_work_terms_on_pages"])
    return {
        "id": row["site_id"], "org": row["org_id"], "name_en": row["name_en"], "name_th": row["name_th"],
        "acronym": row["acronym"], "type": row["org_type"], "level": row["level"], "provinces": provinces,
        "nationwide": nationwide, "city": row["city"],
        "regions": d.union_list([[region_of[c] for c in provinces if c in region_of]]),
        "sw": row["sex_worker_mention"], "led": row["sex_worker_led"],
        "services": sorted(set(split(row["services_mentioned"])), key=lambda s: service_order.get(s, 99)),
        "status": site_status(row, core), "website": row["website"], "social": row["facebook_or_line"],
        "links": split(row["other_urls"]), "evidence": evidence(row, checks), "quotes_found": row["quotes_found"],
        "terms": [t for t in terms if t != BARE_MARK], "bare_term": BARE_MARK in terms,
        "latest": row["latest_activity_seen"],
    }


def province_summary(provinces, sites):
    """covered when a site there has a source naming sex workers, unclear when the province has only other
    candidates, gap when it has none. Nationwide services are counted apart."""
    for p in provinces:
        here = [s for s in sites if p["code"] in s["provinces"]]
        p["n"] = len(here)
        p["n_named"] = sum(s["sw"] == "yes" for s in here)
        p["n_included"] = sum(s["status"] == "included" for s in here)
        p["status"] = "covered" if p["n_named"] else "unclear" if here else "gap"
    return provinces


def public_row(row, status, region_of):
    out = {k: v for k, v in row.items() if k not in PRIVATE_FIELDS}
    codes = split(row["province_codes"])
    out["region"] = ("Nationwide" if codes == [NATIONWIDE]
                     else "; ".join(d.union_list([[region_of[c] for c in codes if c in region_of]])))
    out["meets_inclusion"] = "yes" if status == "included" else "no"
    out["evidence_quotes"] = " | ".join(clean_quote(q) for q in split(row["evidence_quotes"], " | "))
    return {k: out.get(k, "") for k in PUBLIC_FIELDS}


def build(rows, checks, provinces, taxonomy, built=None, spend=(0.0, 0)):
    core = {s["id"] for s in taxonomy["service_types"] if s.get("core")}
    service_order = {s["id"]: i for i, s in enumerate(taxonomy["service_types"])}
    region_of = {p["code"]: p["region"] for p in provinces}
    sites = [site_record(r, checks, core, service_order, region_of) for r in rows]
    provinces = province_summary(provinces, sites)
    counts = Counter(s for site in sites for s in site["services"])
    kept = [c for c in checks if not c["excluded"]]
    pages = {c["evidence_url"]: page_state(c["page"]) for c in kept if c["evidence_url"]}
    meta = {
        "built": built or date.today().isoformat(),
        "sites": len(sites), "orgs": len({s["org"] for s in sites}),
        "included": sum(s["status"] == "included" for s in sites),
        "named": sum(s["sw"] == "yes" for s in sites),
        "unconfirmed": sum(s["status"] == "unconfirmed" for s in sites),
        "unclear": sum(s["status"] == "unclear" for s in sites),
        "led": sum(s["led"] == "yes" for s in sites),
        "nationwide": sum(s["nationwide"] for s in sites),
        "provinces": len(provinces),
        "provinces_with_candidate": sum(p["status"] != "gap" for p in provinces),
        "provinces_covered": sum(p["status"] == "covered" for p in provinces),
        "records": len(kept), "quotes_found": sum(c["quote_check"] == "found" for c in kept),
        "pages": len(pages), "pages_read": sum(v == "read" for v in pages.values()),
        "search_cost": spend[0], "searches": spend[1], "credit": d.CREDIT,
    }
    services = [{"id": s["id"], "en": s["en"], "th": s["th"], "core": bool(s.get("core")), "n": counts[s["id"]]}
                for s in taxonomy["service_types"]]
    data = {"meta": meta, "services": services,
            "org_types": {t["id"]: {"en": t["en"], "th": t["th"]} for t in taxonomy["org_types"]},
            "levels": {t["id"]: {"en": t["en"], "th": t["th"]} for t in taxonomy["levels"]},
            "provinces": provinces, "sites": sites, "columns": PUBLIC_FIELDS}
    public = [public_row(r, s["status"], region_of) for r, s in zip(rows, sites)]
    return data, public


def main(argv=None):
    rows, checks = read_csv(CHECKED_CSV), read_csv(CHECK_CSV)
    taxonomy = json.loads(TAXONOMY_JSON.read_text(encoding="utf-8"))
    data, public = build(rows, checks, load_provinces(), taxonomy, spend=search_spend())
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "sites.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(SITE_DATA / "health_and_help_candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PUBLIC_FIELDS)
        w.writeheader()
        w.writerows(public)
    shutil.copyfile(CODEBOOK, SITE_DATA / "codebook.md")
    m = data["meta"]
    print(f"{m['sites']} sites of {m['orgs']} organisations. {m['included']} meet the inclusion rule, {m['unconfirmed']} name "
          f"sex workers with no core service recorded, {m['unclear']} do not clearly name sex workers.")
    print(f"{m['provinces_with_candidate']} of {m['provinces']} provinces have a candidate and {m['provinces_covered']} a "
          f"source naming sex workers; {m['nationwide']} services are nationwide.")
    print(f"Quotes found on their source page {m['quotes_found']} of {m['records']}. Discovery spent ${m['search_cost']:.2f} "
          f"of ${m['credit']:.2f} on {m['searches']} web searches.")
    print(f"Wrote {SITE_DATA.relative_to(d.ROOT)}/sites.json, health_and_help_candidates.csv and codebook.md")


if __name__ == "__main__":
    main()
