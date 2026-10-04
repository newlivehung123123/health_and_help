#!/usr/bin/env python3
"""Find organisations in Thailand that serve sex workers with sexual health or
mental health services, using Claude Sonnet 5.5 with web search.

Round 1 searches the whole country by type of organisation (5 jobs). Round 2
searches province by province, one job for each of 24 groups of provinces.
Round 3 follows known organisations not yet found, provinces with no findings,
partner lists and Facebook and LINE pages (up to 6 jobs). Each candidate is
recorded with the URL and verbatim quote that support it, for checking in the
next stage.

The project has $27.30 of API credit in all, and discovery may spend $13.00 of
it. Every command adds up the spending in data/discovery/cost_log.csv, test
runs included, and stops before the next request could pass that share.

    python scripts/discover.py --round 1 --dry-run                   prompts and cost estimate, no API calls
    python scripts/discover.py --round 1 --only r1_a_sex_worker_led  one job, to check the setup and the cost
    python scripts/discover.py --round 1                             the rest of the round
    python scripts/discover.py --merge                               writes data/candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import threading
import traceback
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    import anthropic
except ImportError:  # the dry run and the merge work without the SDK
    anthropic = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DISCOVERY = ROOT / "data" / "discovery"
RAW = ROOT / "data" / "raw" / "discovery"
CANDIDATES_CSV = ROOT / "data" / "candidates.csv"

MODEL = "claude-sonnet-5-5"
# USD per million tokens: input, output, 5-minute cache write (1.25 x input), cache read
PRICES = {"claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20), "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20)}
PRICE_SEARCH = 0.01         # USD per web search ($10 per 1,000)

CREDIT = 27.30              # all the API credit the project has, in USD
DISCOVERY_SHARE = 13.00     # the part of the credit discovery may spend, test runs included
TEST_LIMIT = 1.00           # most a test run may spend
REQUEST_MARGIN = 0.40       # room held for each request in progress, raised to the dearest request seen
MAX_COST_PER_SEARCH = 0.10  # a job stops once its cost reaches this times its search cap
BASIC_SEARCH_FROM = "2026-10-04T03:00:00+00:00"  # requests logged earlier used search with dynamic filtering

MAX_TOKENS = 32000
MAX_TOKENS_RETRY = 64000
MAX_REQUESTS_PER_JOB = 14
MAX_CONTINUATIONS = 6
MAX_STREAM_RETRIES = 2
MAX_OVERLOAD_WAITS = 3
MAX_RECORDED_LIST = 400

ROUND_CAPS = {1: 10, 2: 6, 3: 6}  # web searches per job
BIG_CLUSTER_CAP = 8
GAP_PROVINCES_PER_JOB = 3
GAP_SEARCHES_PER_PROVINCE = 2
MAX_SNOWBALL_PAGES = 8
CLINIC_LISTS = ["https://lovefoundation.or.th/en/clinics/"]  # read in round 3 besides the partner lists in the records
TEST_SEARCHES = 3
BIG_CLUSTERS = {"BKK", "CHB", "CNX", "PKT"}
DONE_STATUSES = ("complete", "capped", "no_record", "refused")  # job statuses that a rerun skips
FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5, "max_content_tokens": 12000}
TOOL_NAME = "record_candidates"
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# Platforms where the first part of the path names the account. Posts, photos,
# videos and searches on these platforms give no key, so that two organisations
# are never joined through a platform both of them use.
ACCOUNT_HOSTS = {"facebook.com", "line.me", "page.line.me", "instagram.com", "x.com", "youtube.com", "tiktok.com",
                 "linkedin.com", "linktr.ee", "threads.net", "medium.com", "sites.google.com"}
FACEBOOK_NOT_PAGES = {"watch", "events", "photo", "photos", "video", "videos", "reel", "reels", "stories", "story",
                      "hashtag", "search", "sharer", "marketplace", "gaming", "help", "login", "dialog", "plugins",
                      "media", "notes", "business", "ads", "privacy", "policies", "settings", "home"}
# Short links, Google documents and maps, and LINE or TikTok app links. The whole
# path is kept, which is unique to the page but does not show who owns the page.
OPAQUE_HOSTS = {"bit.ly", "lin.ee", "fb.me", "fb.watch", "youtu.be", "goo.gl", "forms.gle", "g.page", "g.co",
                "tinyurl.com", "t.co", "ow.ly", "cutt.ly", "rb.gy", "is.gd", "s.id", "shorturl.at", "buff.ly",
                "google.com"}
OPAQUE_PARENTS = (".google.com", ".goo.gl", ".line.me", ".tiktok.com")
SOCIAL_HOSTS = {"facebook.com", "fb.me", "fb.watch", "line.me", "page.line.me", "lin.ee", "instagram.com", "x.com",
                "youtube.com", "youtu.be", "tiktok.com", "linkedin.com", "linktr.ee", "threads.net"}
# Hosts that hold pages for many separate units (provincial offices, hospital
# departments, UN country offices). Their first path segment is part of the key.
MULTI_UNIT_DOMAINS = ("go.th", "ac.th", "or.th", "mi.th", "un.org", "who.int", "unaids.org", "unfpa.org",
                      "iom.int", "theglobalfund.org")
LANGUAGE_SEGMENTS = {"en", "th", "my", "lo", "km", "zh", "en-us", "en-gb", "th-th", "index.php", "index.html", "home", "main"}

WRAP_UP = ("You have reached the search limit for this job. Do not run more searches. Call record_candidates "
           "now with every candidate not yet recorded and set job_complete to true.")
NUDGE = ("You ended without calling record_candidates. Call record_candidates now with every candidate you "
         "found, or with an empty list if you found none, and set job_complete to true.")

COST_FIELDS = ["timestamp", "round", "job_id", "model", "request", "stop_reason", "input_tokens",
               "cache_write_tokens", "cache_read_tokens", "output_tokens", "web_searches", "web_fetches", "cost_usd",
               "test"]
CANDIDATE_FIELDS = ["org_id", "site_id", "name_en", "name_th", "acronym", "org_type", "level", "province_codes",
                    "province_en", "city", "sex_worker_mention", "sex_worker_led", "services_mentioned", "website",
                    "facebook_or_line", "other_urls", "partner_list_urls", "evidence_urls", "evidence_quotes",
                    "latest_activity_seen", "notes", "found_in_rounds", "job_ids", "n_records"]


# ---------------------------------------------------------------- configuration

def load_provinces(path=CONFIG / "provinces.csv"):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for key in ("aliases_en", "towns_en", "towns_th"):
            r[key] = [x.strip() for x in r[key].split(";") if x.strip()]
    return rows


def load_taxonomy(path=CONFIG / "taxonomy.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


PROVINCES = load_provinces()
PROVINCE_BY_CODE = {p["code"]: p for p in PROVINCES}
PROVINCE_CODES = [p["code"] for p in PROVINCES]
TAXONOMY = load_taxonomy()
SERVICE_IDS = [s["id"] for s in TAXONOMY["service_types"]]
ORG_TYPES = [o["id"] for o in TAXONOMY["org_types"]]
LEVELS = [x["id"] for x in TAXONOMY["levels"]]

# Organisations named in round 1. Round 3 searches again for any not yet found.
# Aliases are normalised names; short ones must match a name or acronym exactly.
LEADS = [
    ("SWING (Service Workers in Group Foundation)", ["swing", "serviceworkersingroup", "มูลนิธิเพื่อนพนักงานบริการ"]),
    ("Empower Foundation", ["empowerfoundation", "มูลนิธิส่งเสริมโอกาสผู้หญิง"]),
    ("Rainbow Sky Association of Thailand (RSAT)", ["rsat", "rainbowsky", "สมาคมฟ้าสีรุ้งแห่งประเทศไทย"]),
    ("Sisters Foundation", ["sistersfoundation", "มูลนิธิซิสเตอร์"]),
    ("Mplus Foundation", ["mplus", "mplusfoundation", "มูลนิธิเอ็มพลัส"]),
    ("Caremat", ["caremat", "แคร์แมท"]),
    ("Raks Thai Foundation", ["raksthai", "มูลนิธิรักษ์ไทย"]),
    ("Thai Red Cross AIDS Research Centre", ["trcarc", "thairedcrossaids", "ศูนย์วิจัยโรคเอดส์"]),
    ("Institute of HIV Research and Innovation (IHRI)",
     ["ihri", "instituteofhivresearchandinnovation", "สถาบันเพื่อการวิจัยและนวัตกรรมด้านเอชไอวี"]),
    ("Bangrak STIs Center", ["bangrakstis", "bangraksti", "bangrakmedical", "ศูนย์การแพทย์บางรัก"]),
    ("Foundation for AIDS Rights (FAR)", ["foundationforaidsrights", "มูลนิธิเข้าถึงเอดส์"]),
    ("MAP Foundation", ["mapfoundation", "มูลนิธิแมพ"]),
    ("Thai NGO Coalition on AIDS (TNCA)", ["tnca", "ngocoalitiononaids"]),
    ("Thai Network of People Living with HIV/AIDS (TNP+)", ["tnp", "thainetworkofpeoplelivingwithhiv"]),
]


def terms(key):
    return ", ".join(TAXONOMY["search_terms"][key])


SYSTEM = f"""You are helping build an open directory of organisations in Thailand that serve sex workers with sexual health or mental health services. The directory feeds an offline phone app and an SMS service that answer questions such as "where can I get a free HIV test near Pattaya?" using only checked records. A person checks every record you produce against the source you give, so a short list of well-supported candidates is worth more than a long list of guesses.

Who to record
Record an organisation, branch, clinic, drop-in centre, hotline or online service when the sources show both of these:
1. It serves sex workers in Thailand. This includes female, male, transgender and migrant sex workers, people described as entertainment workers or service workers (พนักงานบริการ), and key population programmes that name sex workers among the groups served.
2. It provides, or refers people to, at least one of HIV testing, STI testing or treatment, HIV treatment, PrEP, PEP, condoms or lubricant, or mental health support.
When one condition is clear and the other is not, record the candidate anyway, set sex_worker_mention to match what the source says, and explain the gap in notes. The checking stage decides.

Do not record
- Venues, bars, massage parlours, agencies, escort sites or advertisements for sex work.
- Names of individual people, including staff, peer workers and clients.
- Addresses of drop-in centres, shelters or safe houses that the organisation does not publish itself.
- Private for-profit clinics.
- Government hospitals or offices, unless their own page or an official document names sex workers as a group they serve.

Evidence
- Use only URLs that appeared in your search results or fetched pages. Never construct or guess a URL.
- evidence_quote is a verbatim passage from evidence_url, under 300 characters, in the original language. Choose a passage that shows the sex worker connection or the service, ideally both.
- Prefer a page of the organisation itself, such as its website or Facebook page, as evidence_url. Use a news, research or encyclopedia page only when no page of the organisation appears in the results, and say so in notes.
- Fill website and facebook_or_line whenever the organisation's own site or page appears in the results.
- Leave a field as an empty string or empty list when the sources do not say. Use "unclear" when a source is ambiguous.

Places
- Use the province codes listed below. Record each branch or site as its own candidate with its own province code, because the app answers questions by province.
- Use "nationwide" only for hotlines, online services and LINE official accounts that serve the whole country.

How to search
- Search in Thai first, then English. For migrant sex workers, also search in Burmese, Shan, Lao and Khmer.
- The task states how many searches the job may run. Use all of them, unless every organisation or province in the task has already been searched twice with different queries. Make every search a new query and never run the same query twice.
- Search one province at a time, and never name more than one province in a query.
- Never search the word พนักงานบริการ on its own. The word also means service staff, and searches with it return mostly job advertisements. Use the Thai sex worker terms listed below.
- If the search tool reports that its limit is reached, this job has no searches left. Record every candidate not yet recorded and set job_complete to true.
- Call record_candidates in batches as you go, then make a final call with job_complete set to true. A final call with an empty candidates list is the right way to finish when you found nothing new.
- The task lists organisations already recorded. Do not record them again unless you found a branch or site in a province not listed for them, or the task says otherwise.

Search terms that work in Thailand
- Sex workers, Thai: {terms('sex_workers_th')}
- Sex workers, English: {terms('sex_workers_en')}
- Services, Thai: {terms('services_th')}
- Services, English: {terms('services_en')}

Province codes
{"; ".join(f"{p['code']} {p['name_en']} ({p['name_th']})" for p in PROVINCES)}"""


# ---------------------------------------------------------------- tools

def candidate_schema():
    text = {"type": "string"}
    yes_no = ["yes", "no", "unclear"]
    props = {
        "name_en": {"type": "string", "description": "Name in English as the organisation writes it. Empty if none."},
        "name_th": {"type": "string", "description": "Name in Thai as the organisation writes it. Empty if none."},
        "acronym": text,
        "website": {"type": "string", "description": "Official website URL. Empty if none."},
        "facebook_or_line": {"type": "string",
                             "description": "Official Facebook page URL, LINE URL or LINE ID such as @example. Empty if none."},
        "other_urls": {"type": "array", "items": text,
                       "description": "Other official pages of this organisation, such as Instagram or a branch page. Not news articles."},
        "org_type": {"type": "string", "enum": ORG_TYPES},
        "level": {"type": "string", "enum": LEVELS},
        "province_codes": {"type": "array", "items": {"type": "string", "enum": PROVINCE_CODES + ["nationwide"]},
                           "description": "Province of this site. Use nationwide only for hotlines and online services serving the whole country."},
        "city": {"type": "string", "description": "District or town of this site in English. Empty if not stated."},
        "sex_worker_mention": {"type": "string", "enum": yes_no,
                               "description": "yes if a source names sex workers (พนักงานบริการ) as people this organisation serves."},
        "evidence_url": {"type": "string",
                         "description": "URL of the page that supports this candidate, exactly as it appeared in search results or a fetched page."},
        "evidence_quote": {"type": "string",
                           "description": "Verbatim passage from evidence_url, under 300 characters, in its original language."},
        "services_mentioned": {"type": "array", "items": {"type": "string", "enum": SERVICE_IDS}},
        "sex_worker_led": {"type": "string", "enum": yes_no,
                           "description": "yes if the organisation describes itself as led by sex workers."},
        "partner_list_url": {"type": "string",
                             "description": "URL of a page listing partner or member organisations. Empty if none."},
        "latest_activity_seen": {"type": "string",
                                 "description": "Most recent date of activity seen, as YYYY or YYYY-MM. Empty if none."},
        "notes": {"type": "string",
                  "description": "Anything the checker should know, such as an unclear condition or a page that could not be read."},
    }
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {"type": "array", "items": candidate_schema()},
        "searches_run": {"type": "array", "items": {"type": "string"},
                         "description": "Search queries run since the previous call."},
        "provinces_without_findings": {"type": "array", "items": {"type": "string", "enum": PROVINCE_CODES},
                                       "description": "Provinces in this task where nothing meeting the rules was found."},
        "comments": {"type": "string",
                     "description": "Short note on coverage, dead ends or pages that need a person to check."},
        "job_complete": {"type": "boolean", "description": "true on the final call of this job."},
    },
    "required": ["candidates", "searches_run", "provinces_without_findings", "comments", "job_complete"],
    "additionalProperties": False,
}

RECORD_TOOL = {
    "name": TOOL_NAME,
    "description": ("Record candidate organisations, branches or services found in this job. Call it in batches as "
                    "you go and set job_complete to true on the final call. Each candidate needs a URL you have seen "
                    "and a verbatim quote from that page."),
    "input_schema": RECORD_SCHEMA,
    "eager_input_streaming": True,
}


def search_tool(max_uses):
    # Basic search, which shows the model every result. The version with dynamic filtering makes the model
    # write code to read the results, and in the first job that code failed and ran one query three times.
    # No user_location: the API rejects TH as a search location, and the prompts name each province in Thai.
    return {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}


def tools_for(job):
    tools = [search_tool(job["max_uses"])]
    if job.get("fetch"):
        tools.append(dict(FETCH_TOOL))
    tools.append(RECORD_TOOL)
    return tools


def validate(value, schema, path="$"):
    """Check a parsed tool input against the subset of JSON Schema used above."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{path}: expected an object"]
        errors = []
        props = schema.get("properties", {})
        errors += [f"{path}.{k}: missing" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errors += [f"{path}.{k}: unknown field" for k in value if k not in props]
        for key, sub in props.items():
            if key in value:
                errors += validate(value[key], sub, f"{path}.{key}")
        return errors
    if kind == "array":
        if not isinstance(value, list):
            return [f"{path}: expected an array"]
        errors = []
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
        return errors
    if kind == "string":
        if not isinstance(value, str):
            return [f"{path}: expected a string"]
        allowed = schema.get("enum")
        if allowed and value not in allowed:
            hint = f" Allowed values are {', '.join(allowed)}." if len(allowed) <= 20 else ""
            return [f"{path}: {value!r} is not an allowed value.{hint}"]
        return []
    if kind == "boolean":
        return [] if isinstance(value, bool) else [f"{path}: expected true or false"]
    return []


def check_input(data):
    errors = validate(data, RECORD_SCHEMA)
    if errors or not isinstance(data, dict):
        return errors
    for i, c in enumerate(data["candidates"]):
        path = f"$.candidates[{i}]"
        if not (c["name_en"].strip() or c["name_th"].strip()):
            errors.append(f"{path}: name_en or name_th is required")
        for key in ("website", "evidence_url", "partner_list_url"):
            value = c[key].strip()
            if value and not value.lower().startswith(("http://", "https://")):
                errors.append(f"{path}.{key}: must be a full URL starting with http")
        if c["evidence_quote"].strip() and not c["evidence_url"].strip().lower().startswith("http"):
            errors.append(f"{path}.evidence_url: a quote needs the URL it came from")
    return errors


# ---------------------------------------------------------------- helpers

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def write_jsonl(path, rows, mode="a"):
    with open(path, mode, encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_assistant(messages, content):
    """Add assistant content, extending the previous assistant turn after a pause."""
    if messages and messages[-1]["role"] == "assistant":
        messages[-1]["content"] = list(messages[-1]["content"]) + list(content)
    else:
        messages.append({"role": "assistant", "content": list(content)})


def request_cost(usage, model=MODEL):
    price_input, price_output, price_write, price_read = PRICES[model]
    stu = usage.server_tool_use
    searches = (stu.web_search_requests or 0) if stu else 0
    fetches = (stu.web_fetch_requests or 0) if stu else 0
    tokens = (usage.input_tokens * price_input
              + (usage.cache_creation_input_tokens or 0) * price_write
              + (usage.cache_read_input_tokens or 0) * price_read
              + usage.output_tokens * price_output) / 1e6
    return tokens + searches * PRICE_SEARCH, searches, fetches


def extract_citations(content):
    found = []
    for block in content:
        if getattr(block, "type", None) != "text":
            continue
        for c in getattr(block, "citations", None) or []:
            if getattr(c, "type", None) == "web_search_result_location":
                found.append({"url": c.url, "title": getattr(c, "title", "") or "",
                              "cited_text": getattr(c, "cited_text", "") or ""})
    return found


def container_id(msg):
    container = getattr(msg, "container", None)
    return getattr(container, "id", None) if container else None


def load_env(path=ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():  # -sig drops a byte order mark
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):  # an empty variable in the shell does not hide .env
            os.environ[key] = value


def retryable(error):
    """Overload, rate limit, server and connection errors, including an error
    event inside a stream, which arrives with HTTP status 200."""
    if isinstance(error, anthropic.APIConnectionError):
        return True
    if not isinstance(error, anthropic.APIStatusError):
        return False
    if error.status_code in (408, 409, 429) or error.status_code >= 500:
        return True
    body = error.body if isinstance(error.body, dict) else {}
    detail = body.get("error") if isinstance(body.get("error"), dict) else body
    return detail.get("type") in ("overloaded_error", "api_error", "rate_limit_error")


class JobError(Exception):
    def __init__(self, note, status="failed"):
        super().__init__(note)
        self.status = status


# ---------------------------------------------------------------- organisations and sites

def norm_name(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in text if unicodedata.category(ch)[0] in "LMN")


def split_url(url):
    """Host without www., m. or mobile., the path as lower-case segments, and the query."""
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:  # a malformed address such as an unclosed IPv6 bracket
        return "", [], ""
    if host == "m.me":  # Messenger links name the Facebook page
        host = "facebook.com"
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    if host == "fb.com" or host.endswith(".facebook.com"):
        host = "facebook.com"
    elif host == "twitter.com":
        host = "x.com"
    elif host.endswith(".linkedin.com"):
        host = "linkedin.com"
    return host, [p for p in unquote(parsed.path).lower().split("/") if p], parsed.query


def account_key(host, parts, query):
    """Key for an account on a platform, or "" for a post, photo or search page."""
    first, second = (parts + ["", ""])[:2]
    if host == "facebook.com":
        if first in ("profile.php", "story.php", "permalink.php"):  # id is the page's own number
            page = parse_qs(query).get("id", [""])[0]
            return f"facebook.com/profile.php?id={page}" if page else ""
        if first in FACEBOOK_NOT_PAGES or "." in first:
            return ""
        if first == "pg":
            parts, keep = parts[1:], 1
        elif first == "pages":
            keep = 4 if second == "category" else 3
        elif first == "share":
            keep = 3 if second in ("p", "r", "v", "g") else 2
        elif first in ("groups", "p"):
            keep = 2
        elif first == "people":
            keep = 3
        else:
            keep = 1
    elif host == "line.me":
        handle = next((p for p in parts if p.startswith("@")), "")
        if handle:
            return "line:" + handle
        return "/".join([host] + parts) if parts else ""
    elif host == "page.line.me":
        return "line:@" + first.lstrip("@") if first else ""
    elif host == "youtube.com":
        if first in ("watch", "shorts", "playlist", "live", "embed", "results", "feed", "hashtag", "post"):
            return ""
        keep = 2 if first in ("channel", "c", "user") else 1
    elif host == "instagram.com":
        if first == "stories" and second:
            parts, keep = parts[1:], 1
        elif first in ("p", "reel", "reels", "tv", "explore", "stories", "accounts", "direct"):
            return ""
        else:
            keep = 1
    elif host == "x.com":
        if first in ("i", "hashtag", "search", "intent", "home", "share", "explore", "messages", "settings"):
            return ""
        keep = 1
    elif host == "tiktok.com":
        if not first.startswith("@"):
            return ""
        keep = 1
    elif host == "linkedin.com":
        if first not in ("company", "in", "school", "showcase", "groups"):
            return ""
        keep = 2
    elif host == "sites.google.com":
        keep = 3 if first == "a" else 2 if first in ("view", "site") or "." in first else 1
    else:  # linktr.ee, threads.net, medium.com
        keep = 1
    parts = parts[:keep]
    return "/".join([host] + parts) if parts else ""


def url_key(url):
    """A key that identifies an organisation's own web presence, or "" when the
    text does not identify one, such as a post, a photo or an email address."""
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url and "@" in url and not re.match(r"[\w\-]+(\.[\w\-]+)+(/|$)", url):
        # a LINE ID such as @swing, possibly after a label such as "LINE ID"
        match = re.search(r"(?:^|[\s:：(（])(@[\w.\-]+)", url)
        return "line:" + match.group(1).rstrip(".").lower() if match else ""
    host, parts, query = split_url(url)
    if not host or "." not in host:
        return ""
    if host in ACCOUNT_HOSTS:
        return account_key(host, parts, query)
    if host in OPAQUE_HOSTS or host.endswith(OPAQUE_PARENTS):
        return "/".join([host] + parts) + (f"?{query}" if query else "")
    if any(host == d or host.endswith("." + d) for d in MULTI_UNIT_DOMAINS):
        unit = next((p for p in parts if p not in LANGUAGE_SEGMENTS), "")
        return f"{host}/{unit}" if unit else host
    return host


def is_social(url):
    if url_key(url).startswith("line:"):
        return True
    host = split_url((url or "").strip())[0]
    return host in SOCIAL_HOSTS or host.endswith((".line.me", ".tiktok.com"))


def identity_keys(record):
    return sorted({k for k in (url_key(record.get("website", "")), url_key(record.get("facebook_or_line", ""))) if k})


def name_keys(record):
    names = (record.get("name_en", ""), record.get("name_th", ""), record.get("acronym", ""))
    return sorted({n for n in (norm_name(x) for x in names) if len(n) >= 3})


def build_orgs(records):
    """Group records into organisations by shared website or social page.

    A record without any URL joins an organisation only when its name matches
    exactly one organisation; otherwise records are grouped by name."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    keys = [identity_keys(r) for r in records]
    for ks in keys:
        for k in ks:
            find(k)
        for k in ks[1:]:
            union(ks[0], k)
    by_name = defaultdict(set)
    for r, ks in zip(records, keys):
        if ks:
            for n in name_keys(r):
                by_name[n].add(find(ks[0]))
    assigned = []
    for r, ks in zip(records, keys):
        if ks:
            assigned.append(find(ks[0]))
            continue
        names = name_keys(r)
        roots = {find(x) for n in names for x in by_name.get(n, ())}
        if len(roots) == 1:
            assigned.append(roots.pop())
            continue
        nk = ["name:" + n for n in names] or ["name:unnamed"]
        for k in nk[1:]:
            union(nk[0], k)
        assigned.append(nk[0])
    groups = defaultdict(list)
    for r, root in zip(records, assigned):
        groups[find(root)].append(r)
    return dict(groups)


def mode(values):
    values = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    if not values:
        return ""
    counts = Counter(values)
    best = max(counts.values())
    return next(v for v in values if counts[v] == best)


def union_list(lists):
    seen = []
    for items in lists:
        for x in items or []:
            x = x.strip() if isinstance(x, str) else x
            if x and x not in seen:
                seen.append(x)
    return seen


def best_mention(values):
    for level in ("yes", "unclear", "no"):
        if level in values:
            return level
    return ""


def org_display_name(records):
    en = mode(r.get("name_en", "") for r in records)
    th = mode(r.get("name_th", "") for r in records)
    return " / ".join(x for x in (en, th) if x) or "unnamed"


def province_names(codes):
    return "; ".join("Nationwide" if c == "nationwide" else PROVINCE_BY_CODE[c]["name_en"]
                     for c in codes if c == "nationwide" or c in PROVINCE_BY_CODE)


def site_rows(groups):
    rows = []
    for root, recs in groups.items():
        org_id = "O" + sha1(root)[:8]
        sites = defaultdict(list)
        for r in recs:
            codes = tuple(sorted(set(r.get("province_codes") or [])))
            sites[(codes, (r.get("city") or "").strip().lower())].append(r)
        for codes, city in [k for k in sites if not k[1]]:  # a record without a city joins the only site in its provinces
            named = [k for k in sites if k[0] == codes and k[1]]
            if len(named) == 1:
                sites[named[0]] += sites.pop((codes, city))
        for (codes, city), srecs in sites.items():
            site_id = org_id + "-" + sha1(f"{root}|{','.join(codes)}|{city}")[:6]
            led = [r.get("sex_worker_led", "") for r in srecs]
            rows.append({
                "org_id": org_id,
                "site_id": site_id,
                "name_en": mode(r.get("name_en", "") for r in srecs) or mode(r.get("name_en", "") for r in recs),
                "name_th": mode(r.get("name_th", "") for r in srecs) or mode(r.get("name_th", "") for r in recs),
                "acronym": mode(r.get("acronym", "") for r in recs),
                "org_type": mode(r.get("org_type", "") for r in srecs),
                "level": mode(r.get("level", "") for r in srecs),
                "province_codes": "; ".join(codes),
                "province_en": province_names(codes),
                "city": mode(r.get("city", "") for r in srecs),
                "sex_worker_mention": best_mention([r.get("sex_worker_mention", "") for r in srecs]),
                "sex_worker_led": "yes" if "yes" in led else "unclear" if "unclear" in led else "no" if "no" in led else "",
                "services_mentioned": "; ".join(union_list(r.get("services_mentioned") for r in srecs)),
                "website": mode(r.get("website", "") for r in srecs) or mode(r.get("website", "") for r in recs),
                "facebook_or_line": mode(r.get("facebook_or_line", "") for r in srecs),
                "other_urls": "; ".join(union_list(r.get("other_urls") for r in srecs)),
                "partner_list_urls": "; ".join(union_list([r.get("partner_list_url", "")] for r in srecs)),
                "evidence_urls": "; ".join(union_list([r.get("evidence_url", "")] for r in srecs)),
                "evidence_quotes": " | ".join(union_list([r.get("evidence_quote", "")] for r in srecs)),
                "latest_activity_seen": max((r.get("latest_activity_seen") or "" for r in srecs), default=""),
                "notes": " | ".join(union_list([r.get("notes", "")] for r in srecs)),
                "found_in_rounds": "; ".join(str(x) for x in sorted({r.get("round") for r in srecs if r.get("round")})),
                "job_ids": "; ".join(sorted({r.get("job_id", "") for r in srecs if r.get("job_id")})),
                "n_records": len(srecs),
            })
    rows.sort(key=lambda r: (r["province_codes"] or "~", r["name_en"].casefold() or r["name_th"]))
    return rows


def recorded_lines(records, provinces=(), limit=MAX_RECORDED_LIST):
    """One line per organisation already recorded, those relevant to the job first."""
    items = []
    for recs in build_orgs(records).values():
        codes = sorted({c for r in recs for c in (r.get("province_codes") or [])})
        relevant = bool(set(codes) & set(provinces)) or "nationwide" in codes
        name = org_display_name(recs)
        items.append((not relevant, name.casefold(), f"- {name} [{', '.join(codes) or 'no province'}]"))
    items.sort()
    return [line for *_, line in items[:limit]]


def lead_found(aliases, names):
    aliases = [a for a in (norm_name(x) for x in aliases) if a]  # NFKC splits Thai sara am, so aliases need it too
    return any(a in names or (len(a) >= 6 and any(a in n for n in names)) for a in aliases)


def load_records(out_dir=DISCOVERY, rounds=(1, 2, 3)):
    records = []
    for n in rounds:
        records += read_jsonl(Path(out_dir) / f"round{n}.jsonl")
    return records


def merge(records, out_csv=CANDIDATES_CSV, counts_csv=DISCOVERY / "province_counts.csv", log=print):
    rows = site_rows(build_orgs(records))
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    counts = []
    for p in PROVINCES:
        here = [r for r in rows if p["code"] in r["province_codes"].split("; ")]
        counts.append({"code": p["code"], "name_en": p["name_en"], "name_th": p["name_th"], "region": p["region"],
                       "candidates": len(here),
                       "candidates_sex_worker_named": sum(r["sex_worker_mention"] == "yes" for r in here)})
    Path(counts_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(counts_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(counts[0]))
        w.writeheader()
        w.writerows(counts)
    empty = [c for c in counts if c["candidates"] == 0]
    nationwide = sum("nationwide" in r["province_codes"].split("; ") for r in rows)
    log(f"{len(records)} records, {len({r['org_id'] for r in rows})} organisations, {len(rows)} sites written to {out_csv}")
    log(f"Nationwide services {nationwide}. Provinces with no candidates {len(empty)} of {len(PROVINCES)}"
        + (": " + ", ".join(f"{c['code']} {c['name_en']}" for c in empty) if empty else ""))
    same = Counter((r["org_id"], r["province_codes"]) for r in rows)
    check = [f"{r['name_en'] or r['name_th']} ({r['city'] or 'no city'})" for r in rows
             if same[(r["org_id"], r["province_codes"])] > 1]
    if check:
        log("Sites of one organisation in the same provinces, to check for duplicates: " + "; ".join(check))
    return rows


# ---------------------------------------------------------------- jobs

ROUND1 = [
    ("r1_a_sex_worker_led",
     "Find organisations, networks and groups led by sex workers in Thailand, covering female, male, transgender "
     "and migrant sex workers, and each of their branches and drop-in centres.",
     ["SWING (Service Workers in Group Foundation)", "Empower Foundation",
      "Members in Thailand of the Asia Pacific Network of Sex Workers (APNSW)",
      "Members in Thailand of the Global Network of Sex Work Projects (NSWP)"]),
    ("r1_b_ngo_health",
     "Find non-governmental organisations that provide HIV or STI testing, treatment, PrEP, PEP or condoms to sex "
     "workers in Thailand, including key population-led health services (KPLHS). Record every branch or clinic "
     "separately.",
     ["Rainbow Sky Association of Thailand (RSAT)", "Sisters Foundation", "Mplus Foundation", "Caremat",
      "Raks Thai Foundation", "Thai Red Cross AIDS Research Centre and its Anonymous Clinic",
      "Institute of HIV Research and Innovation (IHRI) and the clinics it runs"]),
    ("r1_c_international",
     "Find international organisations, UN agencies, implementing partners of donors and regional networks that "
     "work with sex workers on HIV, sexual health or mental health in Thailand. Record the Thai organisations that "
     "their reports and grant documents name as implementers, with the province where each one works.",
     ["UNAIDS Thailand", "UNFPA Thailand", "Global Fund grants to Thailand and their sub-recipients", "IOM Thailand",
      "Asia Pacific Network of Sex Workers (APNSW)", "Global Network of Sex Work Projects (NSWP)"]),
    ("r1_d_government",
     "Find government and university services in Thailand whose own pages or official documents name sex workers "
     "as a group they serve with HIV, STI, PrEP, PEP or mental health services.",
     ["Bangrak STIs Center", "Department of Disease Control and its regional Offices of Disease Prevention and Control",
      "Thai Red Cross Anonymous Clinic"]),
    ("r1_e_support",
     "Find mental health, violence, legal and social support for sex workers in Thailand, including hotlines, "
     "online services, LINE official accounts and services in migrant languages (Burmese, Shan, Lao and Khmer).",
     ["Foundation for AIDS Rights (FAR)", "MAP Foundation", "Thai NGO Coalition on AIDS (TNCA)",
      "Thai Network of People Living with HIV/AIDS (TNP+)"]),
]

ROUND2_TASK = """Find organisations, branches and services for sex workers in the provinces below. Work province by province, searching with the Thai province name and town names in Thai first, then in English.

Look for
- branches and drop-in centres of national organisations in these provinces
- local and grassroots groups, including groups led by sex workers
- projects of provincial hospitals, provincial public health offices and Offices of Disease Prevention and Control that name sex workers
- services for migrant sex workers, especially in border and tourist towns"""

ROUND2_CLOSE = ("Record each site as its own candidate with its province code. In your final call, list in "
                "provinces_without_findings every province above where you found nothing that meets the rules.")

SNOWBALL_TASK = ("The pages below list clinics, partners or member organisations. Read each page with web_fetch, "
                 "then record every organisation on the list that meets the rules. A list that does not say whom a "
                 "clinic serves is not evidence that it serves sex workers, so search for each organisation's own "
                 "page to find the evidence URL and quote.")

SOCIAL_TASK = ("The organisations below publish mainly on Facebook or LINE, which often cannot be read directly. For "
               "each one, search for other sources such as its website, news reports, partner lists or government "
               "documents that confirm its services and whether it serves sex workers. This job is an exception to "
               "the already-recorded rule for these organisations. Record each one again with the best evidence you "
               "find, and write \"needs manual check\" in notes when you could not confirm it.")

GAP_TASK = ("Earlier rounds found no candidate with a source that names sex workers in the provinces below. Search "
            "each province on its own, at least twice, with different queries. Pair the Thai province name with "
            "พนักงานบริการทางเพศ, พนักงานบริการหญิง, ผู้ให้บริการทางเพศ or กลุ่มประชากรหลัก, and look for HIV and STI "
            "services for key populations at the provincial hospital (โรงพยาบาลจังหวัด) and its anonymous clinic "
            "(คลินิกนิรนาม), the provincial public health office (สำนักงานสาธารณสุขจังหวัด) and the regional Office of "
            "Disease Prevention and Control. Record what meets the rules, and in your final call list in "
            "provinces_without_findings every province where you still find nothing.")

GAP_RECHECK = ("Recorded in these provinces without a source that names sex workers. Search for a source that does. "
               "This job is an exception to the already-recorded rule for these organisations, so record each one "
               "again when you find such a source.")

LEADS_TASK = ("These organisations are known to work with sex workers or key populations in Thailand but were not "
              "found in earlier rounds. Search for each one and record each of its sites that meets the rules. Say in "
              "comments which ones you could not find or which appear to have closed.")


def province_line(p):
    aliases = f" Also written {', '.join(p['aliases_en'])}." if p["aliases_en"] else ""
    return (f"- {p['code']} {p['name_en']} ({p['name_th']}).{aliases} "
            f"Towns: {', '.join(p['towns_en'])} ({', '.join(p['towns_th'])}).")


def set_cap(job, cap):
    """One request may use the whole allowance, so the search tool's own limit message
    means that the job has no searches left. The tools never change between requests,
    which keeps the cache, so a job that searches past its cap stops at one and a half
    times the cap, and at its cost limit."""
    job["cap"] = cap
    job["max_uses"] = cap
    job["max_searches"] = cap + math.ceil(cap / 2)
    job["max_cost"] = round(MAX_COST_PER_SEARCH * cap, 2)
    return job


def make_job(job_id, round_no, task, *, leads=(), details="", provinces=(), cluster=""):
    job = {"id": job_id, "round": round_no, "task": task, "leads": list(leads), "details": details,
           "provinces": list(provinces), "cluster": cluster, "fetch": round_no == 3}
    return set_cap(job, ROUND_CAPS[round_no])


def round1_jobs():
    return [make_job(job_id, 1, task, leads=leads) for job_id, task, leads in ROUND1]


def round2_jobs():
    clusters = defaultdict(list)
    for p in PROVINCES:
        clusters[p["cluster"]].append(p)
    jobs = []
    for cluster, provs in clusters.items():
        job = make_job(f"r2_{cluster.lower()}", 2, ROUND2_TASK, provinces=[p["code"] for p in provs],
                       details="Provinces\n" + "\n".join(province_line(p) for p in provs) + "\n\n" + ROUND2_CLOSE,
                       cluster=cluster)
        if cluster in BIG_CLUSTERS:
            set_cap(job, BIG_CLUSTER_CAP)
        jobs.append(job)
    return jobs


def gap_jobs(records):
    """Provinces where no record has a source that names sex workers, in jobs of up to three
    neighbouring provinces with two searches for each province. Round 2 put up to four
    provinces in one query and stopped after about half of its searches."""
    named = {c for r in records if r.get("sex_worker_mention") == "yes" for c in (r.get("province_codes") or [])}
    gaps = [p for p in PROVINCES if p["code"] not in named]
    if not gaps:
        return []
    recheck = defaultdict(set)
    for r in records:  # the record's own name, because an organisation's usual name may be another branch
        for code in set(r.get("province_codes") or []) - named:
            recheck[code].add(f"- {org_display_name([r])} [{code}]")
    n_jobs = math.ceil(len(gaps) / GAP_PROVINCES_PER_JOB)
    jobs = []
    for i in range(n_jobs):
        batch = gaps[i * len(gaps) // n_jobs:(i + 1) * len(gaps) // n_jobs]
        codes = [p["code"] for p in batch]
        details = "Provinces\n" + "\n".join(province_line(p) for p in batch)
        lines = sorted(line for code in codes for line in recheck[code])
        if lines:
            details += "\n\n" + GAP_RECHECK + "\n" + "\n".join(lines)
        job = make_job(f"r3_gap_{i + 1}", 3, GAP_TASK, provinces=codes, details=details)
        jobs.append(set_cap(job, GAP_SEARCHES_PER_PROVINCE * len(batch)))
    return jobs


def round3_jobs(records):
    """Follow-up jobs built from the records of rounds 1 and 2, the most useful first:
    known organisations not yet found, clinic and partner lists, provinces where no source
    names sex workers, then organisations known only from Facebook or LINE."""
    jobs = []
    names = {n for r in records for n in name_keys(r)}
    missing = [lead for lead, aliases in LEADS if not lead_found(aliases, names)]
    if missing:
        jobs.append(make_job("r3_leads", 3, LEADS_TASK, details="Organisations\n" + "\n".join(f"- {m}" for m in missing)))

    priority = {}
    for r in records:
        url = (r.get("partner_list_url") or "").strip()
        if url.lower().startswith("http") and url not in CLINIC_LISTS:
            priority[url] = min(priority.get(url, 1), 0 if r.get("sex_worker_mention") == "yes" else 1)
    urls = (CLINIC_LISTS + sorted(priority, key=lambda u: (priority[u], u)))[:MAX_SNOWBALL_PAGES]
    for i in range(0, len(urls), 4):
        jobs.append(make_job(f"r3_snowball_{i // 4 + 1}", 3, SNOWBALL_TASK,
                             details="Pages\n" + "\n".join(f"- {u}" for u in urls[i:i + 4])))

    jobs += gap_jobs(records)

    groups = build_orgs(records)
    social = []
    for recs in groups.values():
        website = mode(r.get("website", "") for r in recs)
        page = mode(r.get("facebook_or_line", "") for r in recs)
        if page and (not website or is_social(website)):
            named = any(r.get("sex_worker_mention") == "yes" for r in recs)
            social.append((not named, org_display_name(recs).casefold(), f"- {org_display_name(recs)}: {page}"))
    if social:
        social.sort()
        jobs.append(make_job("r3_social", 3, SOCIAL_TASK,
                             details="Organisations\n" + "\n".join(x[2] for x in social[:25])))
    return jobs


def done_jobs(jobs_path):
    """Jobs in a job summary file that a rerun skips."""
    return {s["job_id"] for s in read_jsonl(jobs_path) if s.get("status") in DONE_STATUSES}


def unfinished_earlier_jobs(out_dir):
    """Jobs of rounds 1 and 2 that have not finished. Round 3 waits for them, because it searches
    whatever the first two rounds have not covered."""
    done = done_jobs(Path(out_dir) / "jobs_round1.jsonl") | done_jobs(Path(out_dir) / "jobs_round2.jsonl")
    return [j for j in round1_jobs() + round2_jobs() if j["id"] not in done]


def build_jobs(round_no, test=False, out_dir=DISCOVERY):
    if round_no == 1:
        jobs = round1_jobs()
    elif round_no == 2:
        jobs = round2_jobs()
    else:
        jobs = round3_jobs(load_records(out_dir, rounds=(1, 2)))
    if test:
        for job in jobs:
            set_cap(job, TEST_SEARCHES)
    return jobs


def select_jobs(jobs, only):
    wanted = {x.strip().lower() for x in only.split(",") if x.strip()}
    return [j for j in jobs if j["id"].lower() in wanted or j["cluster"].lower() in wanted
            or wanted & {c.lower() for c in j["provinces"]}]


def job_prompt(job, recorded):
    parts = [job["task"]]
    if job["leads"]:
        parts.append("Leads to check first. Record a lead only if a current source supports it, then go beyond "
                     "these leads to find organisations not listed here.\n" + "\n".join(f"- {x}" for x in job["leads"]))
    if job["details"]:
        parts.append(job["details"])
    limit = f"You may run up to {job['cap']} web searches in this job."
    if job["fetch"]:
        limit += f" You may also read up to {FETCH_TOOL['max_uses']} pages with web_fetch."
    parts.append(limit + " Record candidates in batches as you go and finish with a call that sets job_complete to true.")
    parts.append("Already recorded. Do not record these again unless you find a branch or site in a province not "
                 "listed for them.\n" + ("\n".join(recorded) if recorded else "None yet."))
    return "\n\n".join(parts)


def read_cost_log(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def logged_spend(cost_log=DISCOVERY / "cost_log.csv"):
    """Everything discovery has spent so far, test runs included."""
    return sum(float(r.get("cost_usd") or 0) for r in read_cost_log(cost_log))


def spending_limit(share, spent, budget=None, test=False):
    """What the next command may spend: the rest of the share, lowered by --budget and the test limit."""
    limit = share - spent
    if budget is not None:
        limit = min(limit, budget)
    if test:
        limit = min(limit, TEST_LIMIT)
    return limit


def estimate(jobs, model=MODEL, cost_log=DISCOVERY / "cost_log.csv", left=None):
    """Cost of the jobs, from the logged cost per search once requests with this model are logged."""
    caps = sum(j["cap"] for j in jobs)
    n_jobs = f"{len(jobs)} job" if len(jobs) == 1 else f"{len(jobs)} jobs"
    # Requests logged before the switch to basic search cost less for each search and would make the estimate low.
    rows = [r for r in read_cost_log(cost_log)
            if r.get("model") == model and (r.get("timestamp") or "") >= BASIC_SEARCH_FROM]
    searches = sum(int(r["web_searches"] or 0) for r in rows)
    spent = sum(float(r["cost_usd"] or 0) for r in rows)
    if searches:
        per = spent / searches
        high = per * caps
        text = (f"About ${high:.2f} for {n_jobs} with up to {caps} searches, at ${per:.3f} for each search "
                f"including tokens, from {len(rows)} logged request{'' if len(rows) == 1 else 's'} costing ${spent:.2f}.")
    else:
        ratio = PRICES[model][0] / PRICES["claude-opus-5-5"][0]
        low = sum(0.15 * ratio + (PRICE_SEARCH + 0.04 * ratio) * j["cap"] for j in jobs)
        high = sum(0.30 * ratio + (PRICE_SEARCH + 0.09 * ratio) * j["cap"] for j in jobs)
        text = (f"About ${low:.2f} to ${high:.2f} for {n_jobs} with up to {caps} searches. This is a rough "
                f"range, because no requests with {model} are logged yet.")
    if left is not None and high > left:
        text += f" The upper figure is more than the ${left:.2f} this command may spend, so some jobs may not run."
    return text


# ---------------------------------------------------------------- runner

class Runner:
    def __init__(self, client, round_no, *, model=MODEL, effort="medium", limit=DISCOVERY_SHARE,
                 max_tokens=MAX_TOKENS, test=False, out_dir=DISCOVERY, raw_dir=RAW, log=print):
        self.client = client
        self.round = round_no
        self.model = model
        self.effort = effort
        self.limit = limit
        self.margin = REQUEST_MARGIN
        self.in_flight = 0
        self.max_tokens = max_tokens
        self.test = test
        self.out_dir = Path(out_dir)
        self.raw_dir = Path(raw_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        prefix = "test_" if test else ""
        self.prefix = prefix
        self.records_path = self.out_dir / f"{prefix}round{round_no}.jsonl"
        self.jobs_path = self.out_dir / f"{prefix}jobs_round{round_no}.jsonl"
        self.cost_log = self.out_dir / "cost_log.csv"
        self.system = [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]
        self.lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.stop = threading.Event()
        self.stop_reason = ""
        self.spent = 0.0
        self._log = log

    def log(self, text):
        with self.print_lock:
            self._log(text)

    def halt(self, reason):
        with self.lock:
            if not self.stop.is_set():
                self.stop_reason = reason
                self.stop.set()

    def reserve(self):
        """Hold room for one more request, or stop the run when that request could pass the limit."""
        with self.lock:
            room = self.spent + (self.in_flight + 1) * self.margin <= self.limit
            if room:
                self.in_flight += 1
        if not room:
            self.halt(f"the next request could pass the spending limit of ${self.limit:.2f}")
        return room

    def settle(self, cost):
        with self.lock:
            self.in_flight -= 1
            self.spent += cost
            self.margin = max(self.margin, cost)

    def completed_jobs(self):
        """Jobs that a rerun skips, because running them again would most likely buy the same result:
        finished, stopped at one of their own limits, ended without a record, or declined."""
        return done_jobs(self.jobs_path)

    def start_job(self, job):
        """Drop earlier lines for this job and return the list of organisations already recorded."""
        with self.lock:
            for path in (self.records_path, self.jobs_path):
                rows = read_jsonl(path)
                kept = [r for r in rows if r.get("job_id") != job["id"]]
                if len(kept) != len(rows):
                    write_jsonl(path, kept, mode="w")
            records = load_records(self.out_dir, rounds=range(1, job["round"] + 1))
            if self.test:
                records = [r for r in records if r.get("job_id") != job["id"]]
        return recorded_lines(records, job["provinces"])

    def save_records(self, rows):
        with self.lock:
            write_jsonl(self.records_path, rows)

    def log_request(self, job, summary, stop, n_records):
        self.log(f"  {job['id']} request {summary['requests']}: {stop}, searches {summary['searches']}, "
                 f"recorded {n_records}, ${summary['cost_usd']:.2f}")

    def log_cost(self, job, n, msg, cost, searches, fetches):
        u = msg.usage
        row = {"timestamp": now_iso(), "round": job["round"], "job_id": job["id"], "model": self.model, "request": n,
               "stop_reason": msg.stop_reason, "input_tokens": u.input_tokens,
               "cache_write_tokens": u.cache_creation_input_tokens or 0,
               "cache_read_tokens": u.cache_read_input_tokens or 0, "output_tokens": u.output_tokens,
               "web_searches": searches, "web_fetches": fetches, "cost_usd": f"{cost:.4f}", "test": int(self.test)}
        with self.lock:
            new = not self.cost_log.exists()
            with open(self.cost_log, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COST_FIELDS)
                if new:
                    w.writeheader()
                w.writerow(row)

    def call(self, params):
        """One streamed request. Re-issues on unparseable tool input, a rejected
        container, and on overload or rate limits that outlast the SDK retries,
        including errors sent in the middle of a stream."""
        parse_failures = waits = 0
        while True:
            try:
                with self.client.messages.stream(**params) as stream:
                    return stream.get_final_message()
            except ValueError as e:
                parse_failures += 1
                if parse_failures > MAX_STREAM_RETRIES:
                    raise JobError(f"tool input could not be parsed: {e}") from e
            except anthropic.APIError as e:
                if (isinstance(e, anthropic.BadRequestError) and "container" in params
                        and "container" in str(e).lower()):
                    params.pop("container")
                    continue
                if not retryable(e):
                    raise
                waits += 1
                if waits > MAX_OVERLOAD_WAITS:
                    raise
                self.log(f"  {type(e).__name__}, waiting {30 * waits} seconds before trying again")
                if self.stop.wait(30 * waits):
                    raise JobError("run stopped while waiting to retry", status="stopped")

    def run_job(self, job):
        summary = {"job_id": job["id"], "round": job["round"], "status": "skipped", "note": "", "requests": 0,
                   "continuations": 0, "searches": 0, "fetches": 0, "cost_usd": 0.0, "candidates": 0, "searches_run": [],
                   "provinces_without_findings": [], "comments": [], "citations": [], "finished_at": ""}
        if self.stop.is_set():
            summary["note"] = f"not started, {self.stop_reason}"
            return summary
        recorded = self.start_job(job)
        tools = tools_for(job)
        cap = job["cap"]
        messages = [{"role": "user", "content": job_prompt(job, recorded)}]
        raw, citations, records = [], {}, []
        reports = 0
        container = None
        max_tokens = self.max_tokens
        retried_length = nudged = wrapped = False
        status, note = "failed", "interrupted"
        try:
            while True:
                if self.stop.is_set():
                    status, note = "stopped", self.stop_reason
                    break
                if summary["requests"] >= MAX_REQUESTS_PER_JOB:
                    status, note = "capped", f"reached {MAX_REQUESTS_PER_JOB} requests"
                    break
                if summary["searches"] >= job["max_searches"]:
                    status, note = "capped", f"ran {summary['searches']} searches against a limit of {cap}"
                    break
                if summary["cost_usd"] >= job["max_cost"]:
                    status, note = "capped", f"cost ${summary['cost_usd']:.2f} against a limit of ${job['max_cost']:.2f}"
                    break
                if not self.reserve():
                    status, note = "stopped", self.stop_reason
                    break
                params = {"model": self.model, "max_tokens": max_tokens, "system": self.system, "tools": tools,
                          "tool_choice": {"type": "auto"}, "thinking": {"type": "adaptive"},
                          "output_config": {"effort": self.effort}, "cache_control": {"type": "ephemeral"},
                          "messages": messages}
                if container:
                    params["container"] = container
                try:
                    msg = self.call(params)
                except BaseException:
                    self.settle(0.0)
                    raise
                cost, searches, fetches = request_cost(msg.usage, self.model)
                self.settle(cost)
                if container and "container" not in params:  # the API rejected the container
                    container = None
                summary["requests"] += 1
                summary["searches"] += searches
                summary["fetches"] += fetches
                summary["cost_usd"] += cost
                raw.append(msg.model_dump(mode="json"))
                self.log_cost(job, summary["requests"], msg, cost, searches, fetches)
                container = container_id(msg) or container
                for c in extract_citations(msg.content):
                    citations.setdefault((c["url"], c["cited_text"]), c)
                stop = msg.stop_reason
                if stop != "tool_use":  # a tool_use stop is logged once its records are saved
                    self.log_request(job, summary, stop, len(records))

                if stop == "refusal":
                    status, note = "refused", "the model declined this job"
                    break
                if stop == "max_tokens":
                    if not retried_length and max_tokens < MAX_TOKENS_RETRY:
                        retried_length = True  # re-issue the same request with room for the full answer
                        max_tokens = MAX_TOKENS_RETRY
                        continue
                    status, note = "failed", f"output limit of {max_tokens} tokens reached"
                    break
                if stop == "pause_turn":
                    summary["continuations"] += 1
                    if summary["continuations"] > MAX_CONTINUATIONS:
                        status, note = "capped", "too many paused turns"
                        break
                    append_assistant(messages, msg.content)
                    continue
                if stop == "tool_use":
                    append_assistant(messages, msg.content)
                    results, complete, rejected = [], False, False
                    for block in msg.content:
                        if block.type != "tool_use":
                            continue
                        if block.name != TOOL_NAME:
                            rejected = True
                            results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                            "content": f"There is no tool named {block.name}."})
                            continue
                        data = block.input
                        errors = check_input(data)
                        if errors:
                            rejected = True
                            results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                            "content": json.dumps({"INVALID_JSON": json.dumps(data, ensure_ascii=False),
                                                                   "errors": errors[:12]}, ensure_ascii=False)})
                            continue
                        stamped = [{**c, "round": job["round"], "job_id": job["id"], "recorded_at": now_iso(),
                                    "model": self.model} for c in data["candidates"]]
                        records += stamped
                        self.save_records(stamped)
                        reports += 1
                        summary["searches_run"] = union_list([summary["searches_run"], data["searches_run"]])
                        summary["provinces_without_findings"] = union_list(
                            [summary["provinces_without_findings"], data["provinces_without_findings"]])
                        if data["comments"].strip():
                            summary["comments"].append(data["comments"].strip())
                        left = max(cap - summary["searches"], 0)
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "content": f"Recorded {len(stamped)} candidates. {len(records)} recorded in this "
                                                   f"job so far. {summary['searches']} of the {cap} searches allowed in "
                                                   f"this job have run, so {left} {'is' if left == 1 else 'are'} left."})
                        complete = complete or data["job_complete"]
                    self.log_request(job, summary, stop, len(records))
                    if complete and not rejected:  # a rejected batch goes back to the model to correct
                        status, note = "complete", ""
                        break
                    if not results:
                        status, note = "failed", "tool_use stop without a tool call"
                        break
                    content = list(results)
                    if summary["searches"] >= cap and not wrapped:
                        wrapped = True
                        content.append({"type": "text", "text": WRAP_UP})
                    messages.append({"role": "user", "content": content})
                    continue
                if stop == "end_turn":
                    if not reports and not nudged:
                        nudged = True
                        append_assistant(messages, msg.content)
                        messages.append({"role": "user", "content": NUDGE})
                        continue
                    status, note = ("complete", "") if reports else ("no_record", "ended without recording")
                    break
                status, note = "failed", f"stop reason {stop}"
                break
        except JobError as e:
            status, note = e.status, str(e)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError,
                anthropic.BadRequestError) as e:
            status, note = "failed", f"{type(e).__name__}: {e}"
            self.halt(f"{type(e).__name__} in {job['id']}")
        except anthropic.APIError as e:
            status, note = "failed", f"{type(e).__name__}: {e}"
        except Exception as e:
            status, note = "failed", f"unexpected {type(e).__name__}: {e}"
            self.log(traceback.format_exc())
            self.halt(f"unexpected error in {job['id']}")
        finally:
            summary.update(status=status, note=note, candidates=len(records), finished_at=now_iso(),
                           cost_usd=round(summary["cost_usd"], 4), comments=" | ".join(summary["comments"]),
                           citations=list(citations.values()))
            (self.raw_dir / f"{self.prefix}{job['id']}.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
            with self.lock:
                write_jsonl(self.jobs_path, [summary])
        return summary

    def run(self, jobs, workers=3):
        summaries = []
        pool = ThreadPoolExecutor(max_workers=max(1, workers))
        futures = [pool.submit(self.run_job, job) for job in jobs]
        try:
            for future in as_completed(futures):
                s = future.result()
                summaries.append(s)
                self.log(f"{s['job_id']}: {s['status']}{', ' + s['note'] if s['note'] else ''}. "
                         f"{s['candidates']} candidates, {s['searches']} searches, {s['requests']} requests, "
                         f"${s['cost_usd']:.2f}")
        except KeyboardInterrupt:
            self.halt("interrupted")
            self.log("Stopping after the requests in progress finish.")
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        pool.shutdown()
        return summaries


# ---------------------------------------------------------------- command line

def dry_run(args, jobs):
    records = load_records(DISCOVERY, rounds=range(1, args.round + 1))
    print("=" * 30, "System prompt", "=" * 30)
    print(SYSTEM)
    tools = ", ".join(t["name"] for t in tools_for(jobs[0])) if jobs else ""
    print("\nTools:", tools)
    for job in (jobs if args.show_all else jobs[:1]):
        print("\n" + "=" * 30, f"Prompt for {job['id']}", "=" * 30)
        print(job_prompt(job, recorded_lines(records, job["provinces"])))
    print("\n" + "=" * 30, f"Round {args.round} jobs", "=" * 30)
    if args.round == 3:
        if not load_records(DISCOVERY, rounds=(1, 2)):
            print("Rounds 1 and 2 have no records yet, so round 3 shows gap and lead jobs only.")
        waiting = unfinished_earlier_jobs(DISCOVERY)
        if waiting:
            print(f"Rounds 1 and 2 have {len(waiting)} unfinished {'job' if len(waiting) == 1 else 'jobs'}, so a "
                  f"paid run of round 3 will not start yet.")
    for job in jobs:
        where = ", ".join(job["provinces"]) if job["provinces"] else "national"
        print(f"{job['id']:<22} searches up to {job['cap']:>2}   {where}")
    spent = logged_spend(DISCOVERY / "cost_log.csv")
    left = args.share - spent
    print(f"\nDiscovery has spent ${spent:.2f} of its ${args.share:.2f} share, so ${left:.2f} is left.")
    print("Cost estimate:", estimate(jobs, args.model, DISCOVERY / "cost_log.csv", left=left))
    print("No API calls were made.")


def run_round(args, jobs):
    if args.round == 3:
        waiting = unfinished_earlier_jobs(DISCOVERY)
        if waiting:
            ids = [j["id"] for j in waiting]
            named = ", ".join(ids[:8]) + (f" and {len(ids) - 8} more" if len(ids) > 8 else "")
            rounds = sorted({j["round"] for j in waiting})
            again = (f"the --round {rounds[0]} command again first, which reruns" if len(rounds) == 1
                     else "the --round 1 and --round 2 commands again first, which rerun")
            sys.exit(f"Not started. Round 3 searches what rounds 1 and 2 have not covered, and rounds 1 and 2 have "
                     f"{len(ids)} unfinished {'job' if len(ids) == 1 else 'jobs'} ({named}). Run {again} only the "
                     f"unfinished jobs.")
    cost_log = DISCOVERY / "cost_log.csv"
    spent = logged_spend(cost_log)
    limit = spending_limit(args.share, spent, args.budget, args.test)
    if limit <= REQUEST_MARGIN:
        if args.share - spent <= REQUEST_MARGIN:
            sys.exit(f"Not started. Discovery has spent ${spent:.2f} of its ${args.share:.2f} share, which leaves too "
                     f"little for another request. To give discovery more of the ${CREDIT:.2f} credit, run the command "
                     f"again with a higher share, such as --share {args.share + 2:.2f}")
        sys.exit(f"Not started. This command may spend ${limit:.2f}, less than one request can cost.")
    load_env()
    if anthropic is None:
        sys.exit("The anthropic package is missing. Run .venv/bin/pip install -r requirements.txt")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if (ROOT / ".env").exists():
            sys.exit("The key in .env is empty. Open .env, paste the key after ANTHROPIC_API_KEY= and save the file.")
        sys.exit("There is no .env file. Run cp .env.example .env, then paste the key after ANTHROPIC_API_KEY=")
    client = anthropic.Anthropic(max_retries=4)
    runner = Runner(client, args.round, model=args.model, effort=args.effort, limit=limit,
                    max_tokens=args.max_tokens, test=args.test, out_dir=DISCOVERY, raw_dir=RAW)
    if not (args.force or args.test):
        done = runner.completed_jobs()
        skipped = [j["id"] for j in jobs if j["id"] in done]
        if skipped:
            print(f"Skipping {len(skipped)} {'job' if len(skipped) == 1 else 'jobs'} already done (use --force to "
                  f"rerun): {', '.join(skipped)}")
        jobs = [j for j in jobs if j["id"] not in done]
    if not jobs:
        print("Nothing to run.")
        return
    print(f"Round {args.round}{' test' if args.test else ''}: {len(jobs)} {'job' if len(jobs) == 1 else 'jobs'} with "
          f"{args.model} at {args.effort} effort. Discovery has spent ${spent:.2f} of its ${args.share:.2f} share, "
          f"and this command stops before spending more than ${limit:.2f}.")
    print("Estimate:", estimate(jobs, args.model, cost_log, left=limit))
    summaries = runner.run(jobs, workers=1 if args.test else args.workers)
    total = sum(s["cost_usd"] for s in summaries)
    found = sum(s["candidates"] for s in summaries)
    states = Counter(s["status"] for s in summaries)
    print(f"\nDone. {found} candidates, ${total:.2f} spent. "
          + ", ".join(f"{n} {k}" for k, n in sorted(states.items())))
    spent = logged_spend(cost_log)
    print(f"Discovery has now spent ${spent:.2f} of its ${args.share:.2f} share, so ${args.share - spent:.2f} is left.")
    if runner.stop.is_set():
        print(f"Stopped early: {runner.stop_reason}. Run the same command again to resume.")
    print(f"Records {runner.records_path}\nJob summaries {runner.jobs_path}\nCost log {runner.cost_log}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Find organisations serving sex workers in Thailand with Claude and web search.")
    p.add_argument("--round", type=int, choices=[1, 2, 3])
    p.add_argument("--test", action="store_true",
                   help=f"run one job with {TEST_SEARCHES} searches and at most ${TEST_LIMIT:.2f}, into separate test files")
    p.add_argument("--dry-run", action="store_true", help="print prompts, jobs and the cost estimate without API calls")
    p.add_argument("--merge", action="store_true", help="merge all rounds into data/candidates.csv")
    p.add_argument("--only", help="comma-separated job ids, cluster ids or province codes")
    p.add_argument("--effort", default="medium", choices=EFFORTS)
    p.add_argument("--model", default=MODEL, choices=sorted(PRICES))
    p.add_argument("--share", type=float, default=DISCOVERY_SHARE,
                   help=f"most that discovery may spend over all commands, in US dollars (default {DISCOVERY_SHARE:.2f})")
    p.add_argument("--budget", type=float, help="a lower limit in US dollars for this command only")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    p.add_argument("--force", action="store_true", help="rerun jobs already marked complete")
    p.add_argument("--show-all", action="store_true", help="with --dry-run, print every job prompt")
    args = p.parse_args(argv)
    if not args.round and not args.merge:
        p.error("give --round 1, 2 or 3, or --merge")
    if args.round:
        jobs = build_jobs(args.round, test=args.test)
        if args.only:
            jobs = select_jobs(jobs, args.only)
            if not jobs:
                p.error(f"--only {args.only} matches no job in round {args.round}")
        if args.test:
            jobs = jobs[:1]
        if args.dry_run:
            dry_run(args, jobs)
        else:
            try:
                run_round(args, jobs)
            except KeyboardInterrupt:
                print("Stopped. Run the same command again to resume; finished jobs are kept.")
                return 130
    if args.merge:
        merge(load_records())
    return 0


if __name__ == "__main__":
    sys.exit(main())
