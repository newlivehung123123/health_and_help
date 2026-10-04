"""Tests that the figures and file lists in the documentation match the files. No page is downloaded, no API
call is made and no file is written.

Run with  python -m unittest discover -s tests
"""

import csv
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import inclusion_report as inc  # noqa: E402

DOCS = ["README.md", "REPRODUCE.md", "REPLICATION.md", "DATA.md"]
NOT_IN_REPOSITORY = {".git", ".venv", "__pycache__", "raw", ".env", ".DS_Store"}


def read_csv(path):
    with open(ROOT / path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line.strip()]


def text(name):
    return (ROOT / name).read_text(encoding="utf-8")


def repository_files():
    files = []
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and not NOT_IN_REPOSITORY & set(parts) and not path.name.endswith(".pyc"):
            files.append("/".join(parts))
    return sorted(files)


class LayoutTests(unittest.TestCase):
    def test_every_file_is_listed_in_the_readme(self):
        listed = set(re.findall(r"^\| `([^`]+)` \|", text("README.md"), re.M))
        missing = [f for f in repository_files() if f not in listed]
        self.assertEqual(missing, [], "files missing from the layout table of README.md")

    def test_every_listed_file_exists(self):
        listed = re.findall(r"^\| `([^`]+)` \|", text("README.md"), re.M)
        self.assertEqual([f for f in listed if not (ROOT / f).is_file()], [])


class DataSummaryTests(unittest.TestCase):
    def test_rows_and_columns_in_data_md_match_the_files(self):
        table = re.findall(r"^\| `([^`]+)` \| (\d+) \| (\d+) \|", text("DATA.md"), re.M)
        self.assertGreaterEqual(len(table), 14)
        for path, rows, columns in table:
            with self.subTest(path=path):
                if path.endswith(".jsonl"):
                    lines = read_jsonl(path)
                    found = (len(lines), len(lines[0]))
                else:
                    with open(ROOT / path, encoding="utf-8-sig", newline="") as f:
                        lines = list(csv.reader(f))
                    found = (len(lines) - 1, len(lines[0]))
                self.assertEqual(found, (int(rows), int(columns)))


class HeadlineTests(unittest.TestCase):
    def setUp(self):
        self.readme = text("README.md")

    def assertInReadme(self, phrase):
        self.assertIn(phrase, self.readme)

    def test_records_and_sites(self):
        records = sum(len(read_jsonl(f"data/discovery/round{n}.jsonl")) for n in (1, 2, 3))
        merged = read_csv("data/candidates.csv")
        checked = read_csv("data/candidates_checked.csv")
        self.assertInReadme(f"| {records} records |")
        self.assertInReadme(f"| {len(merged)} candidate sites |")
        self.assertInReadme(f"{len(checked)} candidate sites of {len({r['org_id'] for r in checked})} organisations")

    def test_sites_meeting_the_inclusion_rule(self):
        public = read_csv("site/data/health_and_help_candidates.csv")
        passing = [r for r in public if r["meets_inclusion"] == "yes"]
        meta = json.loads(text("site/data/sites.json"))["meta"]
        self.assertEqual(len(passing), meta["included"])
        self.assertInReadme(f"{len(passing)} of the {len(public)} candidate sites, belonging to "
                            f"{len({r['org_id'] for r in passing})} organisations")

    def test_copied_sentences_found(self):
        checks = read_csv("data/source_check.csv")
        kept = [r for r in checks if not r["excluded"]]
        found = sum(r["quote_check"] == "found" for r in checks)
        found_kept = sum(r["quote_check"] == "found" for r in kept)
        meta = json.loads(text("site/data/sites.json"))["meta"]
        self.assertEqual((found_kept, len(kept)), (meta["quotes_found"], meta["records"]))
        self.assertInReadme(f"{found} of the {len(checks)} copied sentences")
        self.assertInReadme(f"{found_kept} of the {len(kept)} copied sentences")

    def test_provinces_and_cost(self):
        meta = json.loads(text("site/data/sites.json"))["meta"]
        self.assertInReadme(f"{meta['provinces_with_candidate']} of {meta['provinces']} provinces")
        self.assertInReadme(f"{meta['provinces_covered']} of {meta['provinces']} provinces")
        log = read_csv("data/discovery/cost_log.csv")
        cost = sum(float(r["cost_usd"]) for r in log)
        searches = sum(int(r["web_searches"]) for r in log)
        self.assertInReadme(f"${cost:.2f} for {len(log)} requests and {searches} web searches")


class InclusionReportTests(unittest.TestCase):
    def test_report_agrees_with_the_public_file(self):
        taxonomy = json.loads(text("config/taxonomy.json"))
        codes = {r["code"] for r in read_csv("config/provinces.csv")}
        public = read_csv("site/data/health_and_help_candidates.csv")
        lines, passing, bad = inc.report(public, taxonomy, codes)
        self.assertEqual({r["site_id"] for r in passing}, {r["site_id"] for r in public if r["meets_inclusion"] == "yes"})
        self.assertEqual(bad, [])
        self.assertIn("Rows whose meets_inclusion column disagrees with the rule 0", lines)

    def test_report_flags_values_outside_the_codebook(self):
        taxonomy = json.loads(text("config/taxonomy.json"))
        row = dict(read_csv("data/candidates_checked.csv")[0], services_mentioned="hiv_testing; massage",
                   province_codes="TH-99", sex_worker_mention="maybe")
        _, _, bad = inc.report([row], taxonomy, {"TH-10"})
        self.assertEqual(len(bad), 3)

    def test_compare_joins_two_runs_by_site_id(self):
        taxonomy = json.loads(text("config/taxonomy.json"))
        core = {s["id"] for s in taxonomy["service_types"] if s.get("core")}
        lines = inc.compare(read_csv("data/candidates_checked.csv"), read_csv("data/candidates.csv"), core)
        self.assertEqual(lines[0], "Sites in both files 50, only in the new file 0, only in the earlier file 3.")


class ProseTests(unittest.TestCase):
    def test_test_count_in_reproduce_md_is_current(self):
        count = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests")).countTestCases()
        self.assertTrue(f"Ran {count} tests" in text("REPRODUCE.md"), f"REPRODUCE.md should say Ran {count} tests")

    def test_documents_use_no_em_or_en_dashes(self):
        for name in DOCS:
            with self.subTest(name=name):
                self.assertNotRegex(text(name), "[–—]")


if __name__ == "__main__":
    unittest.main()
