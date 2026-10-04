#!/usr/bin/env python3
"""Download the page behind each candidate's evidence and check that its quote is on that page.

The check makes no API calls and costs nothing. Every page is saved in data/raw/pages with its
text, so a rerun downloads only the pages not saved yet and the extraction step reads the same
text. Facebook, LINE and X pages need a login, so they are listed for a person to check. The
corrections in config/corrections.csv, which a person writes after reading a source, are applied
to the discovery records first. A correction can also exclude a record that its own source does
not support.

    python scripts/check_sources.py              writes data/source_check.csv and data/candidates_checked.csv
    python scripts/check_sources.py --refetch    downloads every page again
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import logging
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.request
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover as d  # noqa: E402

PAGES = d.ROOT / "data" / "raw" / "pages"
CORRECTIONS_CSV = d.CONFIG / "corrections.csv"
CHECK_CSV = d.ROOT / "data" / "source_check.csv"
CHECKED_CSV = d.ROOT / "data" / "candidates_checked.csv"

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0.0.0 Safari/537.36")
TIMEOUT = 30
MAX_BYTES = 20_000_000
MAX_PDF_PAGES = 300
WORKERS = 8
PIECE = 8          # characters in each piece of a quote looked up on the page
FOUND = 0.9        # share of a quote's pieces that must be on the page for the quote to count as found
PARTLY_FOUND = 0.5
MIN_TEXT = 200     # letters and digits; a page with less was usually built by JavaScript, blocked or scanned
BOT_CHECK = ["client challenge", "enable javascript to proceed", "please enable javascript", "please enable cookies",
             "just a moment", "checking your browser", "verify you are human", "are you a robot",
             "attention required", "captcha", "access denied", "request unsuccessful"]
BOT_CHECK_TEXT = 3000  # letters and digits; a longer page that uses the words above is an ordinary page
SEX_WORK_TERMS = ["sex work", "entertainment worker", "prostitut", "พนักงานบริการทางเพศ", "พนักงานบริการหญิง",
                  "พนักงานบริการชาย", "พนักงานบริการข้ามเพศ", "พนักงานบริการข้ามชาติ", "ผู้ให้บริการทางเพศ",
                  "ผู้ค้าบริการทางเพศ", "หญิงขายบริการ", "ขายบริการทางเพศ", "ค้าประเวณี", "โสเภณี"]
BARE_TERM = "พนักงานบริการ"  # also means service staff, so it is reported apart from the terms above
CODECS = {"tis-620": "cp874", "tis620": "cp874", "iso-8859-11": "cp874", "windows-874": "cp874",
          "x-windows-874": "cp874", "utf8": "utf-8"}

CHECK_FIELDS = ["record", "round", "job_id", "name", "province_codes", "city", "sex_worker_mention",
                "evidence_url", "page", "quote_check", "quote_share_found", "sex_work_terms_on_page",
                "excluded", "evidence_quote", "final_url", "text_file"]
SITE_FIELDS = d.CANDIDATE_FIELDS + ["quotes_found", "sex_work_terms_on_pages", "pages_not_read"]


# ---------------------------------------------------------------- text

class TextParser(HTMLParser):
    SKIP = {"script", "style", "template", "svg"}
    BREAKS = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section",
              "article", "header", "footer", "title", "table", "ul", "ol", "dd", "dt", "blockquote"}
    META = {"description", "og:description", "og:title", "twitter:description"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in self.META:
            self.parts.append("\n" + (a.get("content") or "") + "\n")
        elif tag == "img" and a.get("alt"):
            self.parts.append(" " + a["alt"] + " ")
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(markup):
    parser = TextParser()
    parser.feed(markup)
    parser.close()
    lines = (re.sub(r"[ \t\r\f\v ​]+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
    return "\n".join(line for line in lines if line)


def decode(body, content_type=""):
    """Decode a page, trying UTF-8 first, because Thai sites often declare the wrong encoding."""
    declared = re.findall(r"charset=[\"']?([\w:.-]+)", f"{content_type} {body[:4096].decode('ascii', 'ignore')}", re.I)
    names = [CODECS.get(n.lower(), n.lower()) for n in declared]
    for name in ["utf-8"] + names:
        try:
            return body.decode(name)
        except (LookupError, UnicodeDecodeError):
            continue
    if names and names[0] != "utf-8":
        try:
            return body.decode(names[0], "replace")
        except LookupError:
            pass
    text = body.decode("utf-8", "replace")
    return text if text.count("�") < 50 else body.decode("cp874", "replace")


def page_text(body, content_type=""):
    if body[:5] == b"%PDF-" or "pdf" in content_type.lower():
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(body))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES])
    return html_text(decode(body, content_type))


def squash(text):
    """Letters, digits and marks only, case-folded, so spacing, punctuation and line breaks do not matter."""
    text = unicodedata.normalize("NFKC", unescape(text or "")).casefold()
    return "".join(ch for ch in text if unicodedata.category(ch)[0] in "LMN")


def share_found(quote, page):
    """Share of the quote, in overlapping pieces of PIECE characters, that appears on the squashed page."""
    q = squash(quote)
    if not q:
        return None
    if q in page:
        return 1.0
    if len(q) < PIECE:
        return 0.0
    pieces = {q[i:i + PIECE] for i in range(len(q) - PIECE + 1)}
    return round(sum(p in page for p in pieces) / len(pieces), 2)


def sex_work_terms(page):
    """Terms for sex workers on the squashed page, with the bare term reported only where no qualifier follows it."""
    found = [t for t in SEX_WORK_TERMS if squash(t) in page]
    bare = page.count(squash(BARE_TERM)) - sum(page.count(squash(t)) for t in SEX_WORK_TERMS if t.startswith(BARE_TERM))
    return found + ([f"{BARE_TERM} without a qualifier"] if bare > 0 else [])


def blocked(text):
    """True for the short pages that sites send to programs instead of the page asked for."""
    return len(squash(text)) < BOT_CHECK_TEXT and any(p in text.casefold() for p in BOT_CHECK)


def page_state(text):
    if blocked(text):
        return "not read, blocked by a bot check"
    return "read" if len(squash(text)) >= MIN_TEXT else "little text, probably built by JavaScript, blocked or scanned"


# ---------------------------------------------------------------- download

def lenient_context():
    """For Thai government sites with broken certificate chains or old ciphers; the page is only read as text."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    context.set_ciphers("DEFAULT@SECLEVEL=1")
    return context


def download(url):
    # Some caches keep an old copy for clients that do not ask for compression, as worldvision.or.th
    # did, so the request asks for gzip as every browser does
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8", "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"})
    note = ""
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT)
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        response = urllib.request.urlopen(request, timeout=TIMEOUT, context=lenient_context())
        note = "certificate not verified"
    with response:
        body = response.read(MAX_BYTES)
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)
        return body, response.geturl(), response.headers.get("Content-Type", ""), note


def reason(error):
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, urllib.error.URLError):
        return str(error.reason)[:80]
    return f"{type(error).__name__} {error}"[:80]


def fetch(url, refetch=False, pages=PAGES):
    """Download url once into pages and return what is known about it, its text included.

    A page that could not be read, a bot check included, is not saved, so the next run tries it again."""
    key = d.sha1(url)[:16]
    meta_path, text_path = Path(pages) / f"{key}.json", Path(pages) / f"{key}.txt"
    if meta_path.exists() and text_path.exists() and not refetch:
        text = text_path.read_text(encoding="utf-8")
        if not blocked(text):
            return {**json.loads(meta_path.read_text(encoding="utf-8")), "page": page_state(text), "text": text}
    meta = {"url": url, "fetched_at": d.now_iso()}
    try:
        body, final_url, content_type, note = download(url)
        text = page_text(body, content_type)
    except Exception as e:  # any failure means the page was not read
        return {**meta, "page": f"not read, {reason(e)}", "text": ""}
    if blocked(text):
        for old in Path(pages).glob(f"{key}.*"):  # a copy of the bot check saved by an earlier version
            old.unlink()
        return {**meta, "page": page_state(text), "text": ""}
    meta.update(final_url=final_url, content_type=content_type, bytes=len(body), note=note, page=page_state(text),
                text_file=str(text_path.relative_to(d.ROOT)) if text_path.is_relative_to(d.ROOT) else str(text_path))
    Path(pages).mkdir(parents=True, exist_ok=True)
    (Path(pages) / f"{key}{'.pdf' if body[:5] == b'%PDF-' else '.html'}").write_bytes(body)
    text_path.write_text(text, encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**meta, "text": text}


# ---------------------------------------------------------------- check

def apply_corrections(records, path=CORRECTIONS_CSV, log=print):
    """Copies of the records with the fields that a person corrected after reading a source.

    The field exclude with the value yes marks a record that its own source does not support, and the
    reason is kept with the record."""
    records = [dict(r) for r in records]
    if not Path(path).exists():
        return records
    with open(path, encoding="utf-8-sig", newline="") as f:
        fixes = list(csv.DictReader(f))
    for fix in fixes:
        field, value = fix["field"].strip(), fix["value"].strip()
        hits = [r for r in records if str(r.get("round")) == fix["round"].strip()
                and r.get("job_id") == fix["job_id"].strip() and (r.get("name_en") or r.get("name_th")) == fix["name"].strip()]
        if not hits:
            log(f"Correction matched no record, check config/corrections.csv: {fix['round']} {fix['job_id']} {fix['name']}")
        for r in hits:
            if field == "exclude":
                if value.lower() == "yes":
                    r["excluded"] = (fix.get("reason") or "").strip() or "excluded by a correction"
            else:
                r[field] = [v.strip() for v in value.split(";") if v.strip()] if isinstance(r.get(field), list) else value
    return records


def quote_result(share):
    if share is None:
        return "not checked"
    return "found" if share >= FOUND else "partly found" if share >= PARTLY_FOUND else "not found"


def check(records, fetch_page=fetch, workers=WORKERS):
    """One row per record, saying whether its evidence page was read and whether its quote is on it."""
    urls = sorted({(r.get("evidence_url") or "").strip() for r in records} - {""})
    urls = [u for u in urls if not d.is_social(u)]
    with ThreadPoolExecutor(max(1, workers)) as pool:
        pages = dict(zip(urls, pool.map(fetch_page, urls)))
    squashed = {u: squash(p.get("text", "")) for u, p in pages.items()}
    rows = []
    for i, r in enumerate(records, 1):
        url = (r.get("evidence_url") or "").strip()
        page = pages.get(url)
        state = "no evidence page" if not url else "social page, needs a login" if page is None else page["page"]
        text = squashed.get(url, "")
        share = share_found(r.get("evidence_quote", ""), text) if text else None
        if share is not None and state != "read" and share < FOUND:
            share = None  # the page showed too little text to judge
        rows.append({
            "record": i, "round": r.get("round", ""), "job_id": r.get("job_id", ""),
            "name": r.get("name_en") or r.get("name_th") or "", "province_codes": "; ".join(r.get("province_codes") or []),
            "city": r.get("city", ""), "sex_worker_mention": r.get("sex_worker_mention", ""), "evidence_url": url,
            "page": state, "quote_check": quote_result(share), "quote_share_found": "" if share is None else share,
            "sex_work_terms_on_page": "; ".join(sex_work_terms(text)) if text else "",
            "excluded": r.get("excluded", ""),
            "evidence_quote": r.get("evidence_quote", ""), "final_url": (page or {}).get("final_url", ""),
            "text_file": (page or {}).get("text_file", ""),
        })
    return rows


def site_checks(records, rows):
    """The candidate sites as the merge builds them, with the check results of their records added.

    Excluded records are removed before the merge."""
    kept = [(r, row) for r, row in zip(records, rows) if not r.get("excluded")]
    records, rows = [r for r, _ in kept], [row for _, row in kept]
    org_of = {}
    for root, recs in d.build_orgs(records).items():
        for r in recs:
            org_of[id(r)] = "O" + d.sha1(root)[:8]
    sites = d.site_rows(d.build_orgs(records))
    for s in sites:
        urls, quotes = set(s["evidence_urls"].split("; ")), set(s["evidence_quotes"].split(" | "))
        mine = [row for r, row in zip(records, rows) if org_of[id(r)] == s["org_id"]
                and "; ".join(sorted(set(r.get("province_codes") or []))) == s["province_codes"]
                and row["evidence_url"] in urls and (r.get("evidence_quote") or "").strip() in quotes]
        s["quotes_found"] = f"{sum(row['quote_check'] == 'found' for row in mine)} of {len(mine)}"
        s["sex_work_terms_on_pages"] = "; ".join(d.union_list(row["sex_work_terms_on_page"].split("; ") for row in mine))
        s["pages_not_read"] = "; ".join(d.union_list([row["evidence_url"]] for row in mine if row["page"] != "read"))
    return sites


def write_csv(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def summary(rows, sites, log=print):
    pages = {r["evidence_url"]: r["page"] for r in rows if r["evidence_url"]}
    states = Counter("read" if p == "read" else p.split(",")[0] for p in pages.values())
    log(f"{len(rows)} records with {len(pages)} evidence pages. Pages read {states['read']}, not read {states['not read']}, "
        f"little text {states['little text']}, social pages needing a login {states['social page']}.")
    quotes = Counter(r["quote_check"] for r in rows)
    log(f"Quotes found on their page {quotes['found']} of {len(rows)}, partly found {quotes['partly found']}, "
        f"not found {quotes['not found']}, not checked because the page was not read {quotes['not checked']}.")
    for r in rows:
        if r["quote_check"] != "found" and not r["excluded"]:
            share = f" ({r['quote_share_found']} of the quote)" if r["quote_share_found"] != "" else ""
            log(f"  record {r['record']} {r['name']} [{r['province_codes']}]: {r['quote_check']}{share}, page {r['page']}, {r['evidence_url']}")
    excluded = [r for r in rows if r["excluded"]]
    log(f"Records excluded by {CORRECTIONS_CSV.relative_to(d.ROOT)} {len(excluded)}")
    for r in excluded:
        log(f"  record {r['record']} {r['name']} [{r['province_codes']}]: {r['excluded']}")
    unsupported = [s for s in sites if s["sex_worker_mention"] == "yes" and not s["sex_work_terms_on_pages"]
                   and not set(s["evidence_urls"].split("; ")) <= set(s["pages_not_read"].split("; "))]
    log(f"Sites recorded as naming sex workers whose evidence pages show none of the terms for sex workers {len(unsupported)} of "
        f"{sum(s['sex_worker_mention'] == 'yes' for s in sites)}" + (": " + "; ".join(
            f"{s['name_en'] or s['name_th']} [{s['province_codes']}]" for s in unsupported) if unsupported else ""))
    bare_only = [s for s in sites if s["sex_worker_mention"] == "yes" and s["sex_work_terms_on_pages"] == f"{BARE_TERM} without a qualifier"]
    log(f"Sites recorded as naming sex workers whose evidence pages show only {BARE_TERM} without a qualifier, which can also "
        f"mean service staff, {len(bare_only)}" + (": " + "; ".join(
            f"{s['name_en'] or s['name_th']} [{s['province_codes']}]" for s in bare_only) if bare_only else ""))
    log(f"Written {CHECK_CSV.relative_to(d.ROOT)} ({len(rows)} records) and {CHECKED_CSV.relative_to(d.ROOT)} ({len(sites)} sites)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check that each candidate's quote is on its evidence page. No API calls.")
    parser.add_argument("--refetch", action="store_true", help="download every page again, also those saved earlier")
    parser.add_argument("--workers", type=int, default=WORKERS, help="pages downloaded at the same time")
    args = parser.parse_args(argv)
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    records = apply_corrections(d.load_records())
    rows = check(records, fetch_page=lambda url: fetch(url, refetch=args.refetch), workers=args.workers)
    sites = site_checks(records, rows)
    write_csv(CHECK_CSV, CHECK_FIELDS, rows)
    write_csv(CHECKED_CSV, SITE_FIELDS, sites)
    summary(rows, sites)


if __name__ == "__main__":
    main()
