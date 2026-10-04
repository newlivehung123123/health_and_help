"""Tests for scripts/build_site_data.py. No page is downloaded and no API call is made.

Run with  .venv/bin/python -m unittest discover -s tests
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site_data as b  # noqa: E402

TAXONOMY = {
    "service_types": [{"id": "hiv_testing", "en": "HIV testing", "th": "ตรวจเอชไอวี", "core": True},
                      {"id": "prep", "en": "PrEP", "th": "เพร็พ", "core": True},
                      {"id": "outreach", "en": "Outreach", "th": "งานเชิงรุก", "core": False}],
    "org_types": [{"id": "ngo", "en": "NGO", "th": "มูลนิธิ"}],
    "levels": [{"id": "local", "en": "Local", "th": "ท้องถิ่น"}],
}
PROVINCES = [{"code": "TH-10", "name_en": "Bangkok", "name_th": "กรุงเทพมหานคร", "region": "Central", "lat": 13.76, "lon": 100.50},
             {"code": "TH-21", "name_en": "Rayong", "name_th": "ระยอง", "region": "East", "lat": 12.68, "lon": 101.27},
             {"code": "TH-50", "name_en": "Chiang Mai", "name_th": "เชียงใหม่", "region": "North", "lat": 18.79, "lon": 98.98}]


def site(**fields):
    base = {"org_id": "O1", "site_id": "O1-a", "name_en": "Example Foundation", "name_th": "", "acronym": "",
            "org_type": "ngo", "level": "local", "province_codes": "TH-10", "province_en": "Bangkok", "city": "Bang Rak",
            "sex_worker_mention": "yes", "sex_worker_led": "no", "services_mentioned": "hiv_testing; prep",
            "website": "https://example.org/", "facebook_or_line": "", "other_urls": "", "partner_list_urls": "",
            "evidence_urls": "https://example.org/about", "evidence_quotes": "We test **sex workers** for HIV.",
            "latest_activity_seen": "2026", "notes": "Staff member Somchai answered the phone.", "found_in_rounds": "1",
            "job_ids": "r1_a", "n_records": "1", "quotes_found": "1 of 1", "sex_work_terms_on_pages": "sex work",
            "pages_not_read": ""}
    return {**base, **fields}


def check(**fields):
    base = {"evidence_url": "https://example.org/about", "evidence_quote": "We test **sex workers** for HIV.",
            "quote_check": "found", "page": "read", "excluded": ""}
    return {**base, **fields}


class StatusTests(unittest.TestCase):
    core = {"hiv_testing", "prep"}

    def test_inclusion_needs_a_source_naming_sex_workers_and_a_core_service(self):
        self.assertEqual(b.site_status(site(), self.core), "included")
        self.assertEqual(b.site_status(site(services_mentioned="outreach"), self.core), "unconfirmed")
        self.assertEqual(b.site_status(site(services_mentioned=""), self.core), "unconfirmed")
        self.assertEqual(b.site_status(site(sex_worker_mention="unclear"), self.core), "unclear")

    def test_quotes_lose_bold_markers_and_extra_spaces(self):
        self.assertEqual(b.clean_quote("  We test **sex workers**\n for HIV. "), "We test sex workers for HIV.")


class EvidenceTests(unittest.TestCase):
    def test_check_rows_join_the_site_by_page_and_quote(self):
        rows = [check(), check(evidence_url="https://other.org/", evidence_quote="Other quote"),
                check(page="social page, needs a login", quote_check="not checked")]
        items = b.evidence(site(), rows)
        self.assertEqual(items, [{"url": "https://example.org/about", "quote": "We test sex workers for HIV.",
                                  "check": "found", "page": "read"}])

    def test_excluded_records_are_not_evidence(self):
        self.assertEqual(b.evidence(site(), [check(excluded="The page lists another organisation.")]), [])


class BuildTests(unittest.TestCase):
    def build(self, rows, checks=None):
        provinces = [dict(p) for p in PROVINCES]
        return b.build(rows, checks if checks is not None else [check()], provinces, TAXONOMY, built="2026-10-04")

    def test_province_status_follows_the_sites_there(self):
        rows = [site(),
                site(org_id="O2", site_id="O2-a", province_codes="TH-21", sex_worker_mention="unclear"),
                site(org_id="O3", site_id="O3-a", province_codes="nationwide", province_en="Nationwide")]
        data, _ = self.build(rows)
        status = {p["code"]: (p["status"], p["n"]) for p in data["provinces"]}
        self.assertEqual(status, {"TH-10": ("covered", 1), "TH-21": ("unclear", 1), "TH-50": ("gap", 0)})
        nationwide = data["sites"][2]
        self.assertTrue(nationwide["nationwide"])
        self.assertEqual(nationwide["provinces"], [])
        self.assertEqual(data["meta"]["provinces_with_candidate"], 2)
        self.assertEqual(data["meta"]["provinces_covered"], 1)
        self.assertEqual(data["meta"]["nationwide"], 1)

    def test_a_site_in_two_provinces_counts_in_both_regions(self):
        data, public = self.build([site(province_codes="TH-10; TH-50", province_en="Bangkok; Chiang Mai")])
        self.assertEqual(data["sites"][0]["regions"], ["Central", "North"])
        self.assertEqual([p["n"] for p in data["provinces"]], [1, 0, 1])
        self.assertEqual(public[0]["region"], "Central; North")

    def test_bare_term_is_a_flag_and_not_a_term(self):
        data, _ = self.build([site(sex_work_terms_on_pages="พนักงานบริการ without a qualifier")])
        self.assertEqual(data["sites"][0]["terms"], [])
        self.assertTrue(data["sites"][0]["bare_term"])

    def test_services_follow_the_taxonomy_order_and_are_counted(self):
        data, _ = self.build([site(services_mentioned="prep; outreach; hiv_testing")])
        self.assertEqual(data["sites"][0]["services"], ["hiv_testing", "prep", "outreach"])
        self.assertEqual({s["id"]: s["n"] for s in data["services"]}, {"hiv_testing": 1, "prep": 1, "outreach": 1})

    def test_public_files_exclude_notes_and_run_bookkeeping(self):
        data, public = self.build([site()])
        self.assertEqual(list(public[0]), b.PUBLIC_FIELDS)
        self.assertEqual(public[0]["meets_inclusion"], "yes")
        self.assertEqual(public[0]["evidence_quotes"], "We test sex workers for HIV.")
        text = json.dumps(data, ensure_ascii=False) + json.dumps(public, ensure_ascii=False)
        self.assertNotIn("Somchai", text)
        self.assertNotIn("r1_a", text)

    def test_quote_counts_use_only_the_records_kept(self):
        checks = [check(), check(quote_check="not checked", page="not read, HTTP 403", evidence_quote="Q2"),
                  check(excluded="wrong province")]
        data, _ = self.build([site()], checks)
        self.assertEqual((data["meta"]["records"], data["meta"]["quotes_found"]), (2, 1))


class ProvincePointTests(unittest.TestCase):
    def test_every_province_has_a_point_inside_thailand(self):
        provinces = b.load_provinces()
        self.assertEqual(len(provinces), 77)
        self.assertEqual(len({(p["lat"], p["lon"]) for p in provinces}), 77)


if __name__ == "__main__":
    unittest.main()
