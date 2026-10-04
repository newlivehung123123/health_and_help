"""Tests for scripts/check_sources.py. No page is downloaded and no API call is made.

Run with  .venv/bin/python -m unittest discover -s tests
"""

import csv
import gzip
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_sources as c  # noqa: E402

PAGE = ("<html><body><p>" + "The clinic offers free HIV testing for sex workers in Bangkok. " * 10
        + "</p></body></html>").encode()
CHALLENGE = ("Client Challenge\nJavaScript is disabled in your browser.\nPlease enable JavaScript to proceed.\n"
             "A required part of this site couldn’t load.")


def record(**fields):
    base = {"round": 1, "job_id": "r1_a", "name_en": "Example Foundation", "name_th": "", "acronym": "",
            "website": "https://example.org/", "facebook_or_line": "", "other_urls": [], "province_codes": ["TH-10"],
            "city": "Bang Rak", "sex_worker_mention": "yes", "evidence_url": "https://example.org/about",
            "evidence_quote": "We offer HIV testing for sex workers.", "services_mentioned": ["hiv_testing"]}
    return {**base, **fields}


class TextTests(unittest.TestCase):
    def test_html_text_skips_scripts_and_keeps_meta_and_alt_text(self):
        html = ('<html><head><title>Clinic</title><meta name="description" content="Free HIV testing">'
                '<script>var x = "hidden";</script><style>p {color: red}</style></head>'
                '<body><p>First&nbsp;line</p><div>Second <b>line</b></div><img alt="Map of the clinic"></body></html>')
        text = c.html_text(html)
        for kept in ("Free HIV testing", "Map of the clinic", "First line", "Second line"):
            self.assertIn(kept, text)
        self.assertNotIn("hidden", text)
        self.assertNotIn("color", text)

    def test_decode_reads_thai_pages_in_either_encoding(self):
        thai = "ตรวจเอชไอวีฟรีสำหรับพนักงานบริการหญิง " * 5
        declared = f'<meta charset="tis-620">{thai}'
        self.assertEqual(c.decode(declared.encode("cp874")), declared)
        self.assertEqual(c.decode(declared.encode("utf-8")), declared)  # declares TIS-620 but is written in UTF-8
        self.assertEqual(c.decode(thai.encode("cp874"), "text/html"), thai)  # declares nothing


class QuoteTests(unittest.TestCase):
    def test_share_found_ignores_spacing_punctuation_and_case(self):
        page = c.squash("ให้บริการ ตรวจเอชไอวี\nและซิฟิลิส ฟรี  สำหรับพนักงานบริการหญิง. Open Monday–Friday.")
        self.assertEqual(c.share_found("ตรวจเอชไอวีและซิฟิลิส ฟรี", page), 1.0)
        self.assertEqual(c.share_found("OPEN monday - friday", page), 1.0)

    def test_quote_joined_from_two_places_is_partly_found(self):
        page = c.squash("5. SWING Silom branch, phone 0 2632 9502. 6. RSAT Nakhon Pathom, phone 09 4563 4537.")
        share = c.share_found("SWING Nakhon Pathom, phone 09 4563 4537", page)
        self.assertEqual(c.quote_result(share), "partly found")

    def test_quote_results(self):
        self.assertEqual(c.share_found("We offer PrEP to migrants.", c.squash("We offer HIV testing for sex workers.")), 0.0)
        self.assertIsNone(c.share_found("", "anything"))
        self.assertEqual(c.share_found("short", c.squash("a longer page")), 0.0)
        self.assertEqual([c.quote_result(s) for s in (None, 0.95, 0.6, 0.1)],
                         ["not checked", "found", "partly found", "not found"])

    def test_sex_work_terms_report_the_bare_term_apart(self):
        self.assertEqual(c.sex_work_terms(c.squash("บริการสำหรับพนักงานบริการหญิง")), ["พนักงานบริการหญิง"])
        self.assertEqual(c.sex_work_terms(c.squash("รับสมัครพนักงานบริการลูกค้า")), ["พนักงานบริการ without a qualifier"])
        self.assertEqual(c.sex_work_terms(c.squash("หญิงขายบริการ และ Sex Workers")), ["sex work", "หญิงขายบริการ"])
        self.assertEqual(c.sex_work_terms(c.squash("HIV testing for everyone")), [])


class PageStateTests(unittest.TestCase):
    def test_bot_check_page_is_not_read(self):
        self.assertTrue(c.blocked(CHALLENGE))
        self.assertEqual(c.page_state(CHALLENGE), "not read, blocked by a bot check")

    def test_long_page_that_mentions_javascript_is_read(self):
        text = "Our clinic offers free HIV testing every weekday. " * 100 + "Please enable JavaScript to see the map."
        self.assertFalse(c.blocked(text))
        self.assertEqual(c.page_state(text), "read")

    def test_short_page_has_little_text(self):
        self.assertTrue(c.page_state("Loading").startswith("little text"))


class FetchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pages = Path(tmp.name)

    def test_page_is_saved_once_and_read_from_disk_after(self):
        with mock.patch.object(c, "download", return_value=(PAGE, "https://example.org/a", "text/html", "")) as dl:
            first = c.fetch("https://example.org/a", pages=self.pages)
            second = c.fetch("https://example.org/a", pages=self.pages)
        self.assertEqual(dl.call_count, 1)
        self.assertEqual((first["page"], second["page"]), ("read", "read"))
        self.assertEqual(second["text"], first["text"])
        self.assertEqual(len(list(self.pages.glob("*"))), 3)  # metadata, text and the page itself

    def test_failure_and_bot_check_are_not_saved(self):
        error = c.urllib.error.HTTPError("https://example.org/b", 403, "Forbidden", {}, None)
        with mock.patch.object(c, "download", side_effect=error):
            self.assertEqual(c.fetch("https://example.org/b", pages=self.pages)["page"], "not read, HTTP 403")
        with mock.patch.object(c, "download", return_value=(CHALLENGE.encode(), "https://example.org/c", "text/plain", "")):
            result = c.fetch("https://example.org/c", pages=self.pages)
        self.assertEqual((result["page"], result["text"]), ("not read, blocked by a bot check", ""))
        self.assertEqual(list(self.pages.glob("*")), [])

    def test_saved_bot_check_is_downloaded_again(self):
        key = c.d.sha1("https://example.org/d")[:16]
        (self.pages / f"{key}.json").write_text(json.dumps({"url": "https://example.org/d", "page": "read"}))
        (self.pages / f"{key}.txt").write_text(CHALLENGE, encoding="utf-8")
        with mock.patch.object(c, "download", return_value=(PAGE, "https://example.org/d", "text/html", "")) as dl:
            result = c.fetch("https://example.org/d", pages=self.pages)
        self.assertEqual(dl.call_count, 1)
        self.assertEqual(result["page"], "read")

    def test_download_asks_for_gzip_and_unpacks_it(self):
        body = "<p>ตรวจเอชไอวี</p>".encode()

        class Response(io.BytesIO):
            headers = {"Content-Encoding": "gzip", "Content-Type": "text/html; charset=utf-8"}

            def geturl(self):
                return "https://example.org/final"

        with mock.patch.object(c.urllib.request, "urlopen", return_value=Response(gzip.compress(body))) as urlopen:
            got, final_url, _, note = c.download("https://example.org/start")
        self.assertIn("gzip", urlopen.call_args[0][0].get_header("Accept-encoding"))
        self.assertEqual((got, final_url, note), (body, "https://example.org/final", ""))


class CorrectionTests(unittest.TestCase):
    def write(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "corrections.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["round", "job_id", "name", "field", "value", "reason"])
            w.writerows(rows)
        return path

    def test_corrections_change_only_the_matching_record(self):
        a, b = record(job_id="r1_d", city="Sathorn"), record(round=3, job_id="r3_social", city="Bang Rak")
        path = self.write([["3", "r3_social", "Example Foundation", "city", "Sathorn", "address on the page"],
                           ["3", "r3_social", "Example Foundation", "province_codes", "TH-10; TH-11", "two provinces"]])
        fixed = c.apply_corrections([a, b], path=path, log=lambda *_: None)
        self.assertEqual([r["city"] for r in fixed], ["Sathorn", "Sathorn"])
        self.assertEqual([r["province_codes"] for r in fixed], [["TH-10"], ["TH-10", "TH-11"]])
        self.assertEqual((b["city"], b["province_codes"]), ("Bang Rak", ["TH-10"]))  # the discovery records stay as they were

    def test_exclusion_keeps_its_reason_and_an_unmatched_correction_is_reported(self):
        logs = []
        path = self.write([["2", "r1_a", "Example Foundation", "exclude", "yes", "the page lists another organisation"],
                           ["2", "r2_x", "Missing Foundation", "city", "Hat Yai", "no such record"]])
        fixed = c.apply_corrections([record(round=2)], path=path, log=logs.append)
        self.assertEqual(fixed[0]["excluded"], "the page lists another organisation")
        self.assertEqual(len(logs), 1)
        self.assertIn("Missing Foundation", logs[0])

    def test_missing_file_changes_nothing(self):
        self.assertEqual(c.apply_corrections([record()], path=Path("/nonexistent/corrections.csv")), [record()])


class CheckTests(unittest.TestCase):
    def test_one_row_per_record(self):
        pages = {"https://example.org/about": {"page": "read", "text": "We offer HIV testing for sex workers. " * 20},
                 "https://example.org/gone": {"page": "not read, HTTP 404", "text": ""}}
        fetched = []

        def fetch_page(url):
            fetched.append(url)
            return pages[url]

        records = [record(), record(evidence_quote="We offer PrEP to migrants."),
                   record(evidence_url="https://example.org/gone"), record(evidence_url="https://www.facebook.com/example"),
                   record(evidence_url="", excluded="no source")]
        rows = c.check(records, fetch_page=fetch_page, workers=1)
        self.assertEqual(sorted(fetched), ["https://example.org/about", "https://example.org/gone"])
        self.assertEqual([r["quote_check"] for r in rows], ["found", "not found", "not checked", "not checked", "not checked"])
        self.assertEqual([r["page"] for r in rows][2:], ["not read, HTTP 404", "social page, needs a login", "no evidence page"])
        self.assertEqual(rows[0]["sex_work_terms_on_page"], "sex work")
        self.assertEqual(rows[4]["excluded"], "no source")

    def test_sites_drop_excluded_records_and_join_records_of_one_city(self):
        records = [record(job_id="r1_d", city="Sathorn", evidence_url="https://example.org/a",
                          evidence_quote="Quote one about HIV testing."),
                   record(round=3, job_id="r3_social", city="Sathorn", evidence_url="https://example.org/b",
                          evidence_quote="Quote two about PrEP services."),
                   record(name_en="Other Foundation", website="https://other.org/", city="Hat Yai", province_codes=["TH-90"],
                          excluded="the page lists another organisation")]
        text = "Quote one about HIV testing. Quote two about PrEP services for sex workers. " * 10
        rows = c.check(records, fetch_page=lambda url: {"page": "read", "text": text}, workers=1)
        sites = c.site_checks(records, rows)
        self.assertEqual([(s["n_records"], s["quotes_found"], s["pages_not_read"]) for s in sites], [(2, "2 of 2", "")])
        logs = []
        c.summary(rows, sites, log=logs.append)
        self.assertTrue(any("the page lists another organisation" in line for line in logs))
        self.assertTrue(any("show none of the terms for sex workers 0 of 1" in line for line in logs))

    def test_site_with_only_the_bare_term_is_listed(self):
        records = [record(evidence_quote="บริการตรวจเอชไอวีสำหรับพนักงานบริการ")]
        text = "บริการตรวจเอชไอวีสำหรับพนักงานบริการ " * 20
        rows = c.check(records, fetch_page=lambda url: {"page": "read", "text": text}, workers=1)
        logs = []
        c.summary(rows, c.site_checks(records, rows), log=logs.append)
        self.assertTrue(any("show none of the terms for sex workers 0 of 1" in line for line in logs))
        self.assertTrue(any("can also mean service staff, 1: Example Foundation [TH-10]" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
