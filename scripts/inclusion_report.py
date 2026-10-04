#!/usr/bin/env python3
"""Report how many candidate sites meet the inclusion rule of codebook.md, and check their coded values.

The report makes no API calls, downloads nothing and writes no file. It reads a file of candidate sites in
the layout of data/candidates_checked.csv or site/data/health_and_help_candidates.csv, together with
config/taxonomy.json and config/provinces.csv. A site meets the rule when sex_worker_mention is yes and
services_mentioned includes at least one of the nine core services, the same test that
scripts/build_site_data.py applies. Two further clauses of the rule cannot be computed from the file, so the
report lists the government sites that pass the test, for a person to confirm that the facility's own pages
name sex workers, and leaves the exclusion of private for-profit clinics to that person.

    python scripts/inclusion_report.py                                                reads data/candidates_checked.csv
    python scripts/inclusion_report.py site/data/health_and_help_candidates.csv      any file with the same columns
    python scripts/inclusion_report.py new.csv --compare data/candidates_checked.csv  also compares two runs by site_id
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "candidates_checked.csv"
TAXONOMY_JSON = ROOT / "config" / "taxonomy.json"
PROVINCES_CSV = ROOT / "config" / "provinces.csv"
NATIONWIDE = "nationwide"
MENTION_VALUES = {"yes", "no", "unclear"}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def meets_rule(row, core):
    """yes when a source names sex workers and the site offers at least one core service, as in codebook.md."""
    return row["sex_worker_mention"] == "yes" and bool(core & set(split(row["services_mentioned"])))


def problems(row, taxonomy, province_codes):
    """Coded values in the row that the codebook does not allow."""
    services = {s["id"] for s in taxonomy["service_types"]}
    found = []
    for code in split(row["services_mentioned"]):
        if code not in services:
            found.append(f"service {code!r} is not in Table 1")
    for code in split(row["province_codes"]):
        if code != NATIONWIDE and code not in province_codes:
            found.append(f"province {code!r} is not in config/provinces.csv")
    if row["org_type"] and row["org_type"] not in {t["id"] for t in taxonomy["org_types"]}:
        found.append(f"org_type {row['org_type']!r} is not in Table 3")
    if row["level"] and row["level"] not in {t["id"] for t in taxonomy["levels"]}:
        found.append(f"level {row['level']!r} is not in Table 3")
    for key in ("sex_worker_mention", "sex_worker_led"):
        if row[key] and row[key] not in MENTION_VALUES:
            found.append(f"{key} {row[key]!r} is not yes, no or unclear")
    return found


def report(rows, taxonomy, province_codes):
    core = {s["id"] for s in taxonomy["service_types"] if s.get("core")}
    passing = [r for r in rows if meets_rule(r, core)]
    lines = [f"{len(passing)} of {len(rows)} sites, of {len({r['org_id'] for r in passing})} organisations, meet the "
             f"inclusion rule, out of {len({r['org_id'] for r in rows})} organisations in the file."]
    mention = Counter(r["sex_worker_mention"] for r in rows)
    no_core = sum(r["sex_worker_mention"] == "yes" and not meets_rule(r, core) for r in rows)
    lines.append(f"Sites whose sources name sex workers {mention['yes']}, of which {no_core} have no core service "
                 f"recorded. Sites whose sources do not clearly name sex workers {len(rows) - mention['yes']}.")
    if "meets_inclusion" in rows[0]:
        differ = [r["site_id"] for r in rows if (r["meets_inclusion"] == "yes") != meets_rule(r, core)]
        lines.append(f"Rows whose meets_inclusion column disagrees with the rule {len(differ)}"
                     + (": " + ", ".join(differ) if differ else ""))
    government = [r for r in passing if r["org_type"] == "government"]
    lines.append(f"Government sites that meet the rule {len(government)}. Confirm for each that the facility's own "
                 f"pages name sex workers" + (": " + "; ".join(
                     f"{r['site_id']} {r['name_en'] or r['name_th']}" for r in government) if government else "."))
    bad = [(r["site_id"], p) for r in rows for p in problems(r, taxonomy, province_codes)]
    lines.append(f"Coded values not allowed by the codebook {len(bad)}")
    lines += [f"  {site_id}: {text}" for site_id, text in bad]
    return lines, passing, bad


def compare(rows, old_rows, core):
    """Sites of two runs joined by site_id, which the merge computes from the organisation's web address key,
    the provinces and the city, so a site recorded alike in both runs keeps its identifier."""
    new, old = {r["site_id"]: r for r in rows}, {r["site_id"]: r for r in old_rows}
    both = sorted(new.keys() & old.keys())
    gained = [s for s in both if meets_rule(new[s], core) and not meets_rule(old[s], core)]
    lost = [s for s in both if meets_rule(old[s], core) and not meets_rule(new[s], core)]

    def name(r):
        return f"{r['site_id']} {r['name_en'] or r['name_th']}"

    lines = [f"Sites in both files {len(both)}, only in the new file {len(new.keys() - old.keys())}, only in the "
             f"earlier file {len(old.keys() - new.keys())}.",
             f"Sites in both files that now meet the inclusion rule and did not before {len(gained)}"
             + (": " + "; ".join(name(new[s]) for s in gained) if gained else ""),
             f"Sites in both files that met the inclusion rule before and no longer do {len(lost)}"
             + (": " + "; ".join(name(new[s]) for s in lost) if lost else "")]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply the inclusion rule of codebook.md to a file of candidate "
                                                 "sites. Reads files only.")
    parser.add_argument("csv", nargs="?", default=str(DEFAULT_CSV), help="candidate sites, default %(default)s")
    parser.add_argument("--compare", metavar="EARLIER_CSV", help="an earlier file of candidate sites to compare by site_id")
    args = parser.parse_args(argv)
    rows = read_csv(args.csv)
    if not rows:
        sys.exit(f"{args.csv} has no rows")
    taxonomy = json.loads(TAXONOMY_JSON.read_text(encoding="utf-8"))
    province_codes = {r["code"] for r in read_csv(PROVINCES_CSV)}
    lines, _, bad = report(rows, taxonomy, province_codes)
    if args.compare:
        core = {s["id"] for s in taxonomy["service_types"] if s.get("core")}
        lines += compare(rows, read_csv(args.compare), core)
    print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
