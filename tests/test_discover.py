"""Tests for scripts/discover.py. No API calls are made.

Run with  .venv/bin/python -m unittest discover tests
"""

import copy
import csv
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import anthropic  # noqa: E402
import httpx2  # noqa: E402

import discover as d  # noqa: E402

IDS = itertools.count(1)
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def message(stop, content, searches=0, container=None, input_tokens=1000):
    data = {"id": f"msg_{next(IDS)}", "type": "message", "role": "assistant", "model": d.MODEL,
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": 500, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0,
                      "server_tool_use": {"web_search_requests": searches, "web_fetch_requests": 0}}}
    if container:
        data["container"] = {"id": container, "expires_at": "2026-10-04T12:00:00Z"}
    return anthropic.types.Message.model_validate(data)


def text(value):
    return {"type": "text", "text": value}


def search(query="พนักงานบริการ"):
    n = next(IDS)
    return [{"type": "server_tool_use", "id": f"srvtoolu_{n}", "name": "web_search", "input": {"query": query}},
            {"type": "web_search_tool_result", "tool_use_id": f"srvtoolu_{n}",
             "content": [{"type": "web_search_result", "url": "https://example.org", "title": "Example",
                          "encrypted_content": "x", "page_age": None}]}]


def candidate(**overrides):
    c = {"name_en": "Example Foundation", "name_th": "", "acronym": "", "website": "https://example.org",
         "facebook_or_line": "", "other_urls": [], "org_type": "ngo", "level": "national",
         "province_codes": ["TH-10"], "city": "Bang Rak", "sex_worker_mention": "yes",
         "evidence_url": "https://example.org/about", "evidence_quote": "We provide HIV testing for sex workers.",
         "services_mentioned": ["hiv_testing"], "sex_worker_led": "no", "partner_list_url": "",
         "latest_activity_seen": "2026", "notes": ""}
    c.update(overrides)
    return c


def record_call(candidates, complete, tool_id=None, **extra):
    data = {"candidates": candidates, "searches_run": ["พนักงานบริการ ตรวจเอชไอวี"],
            "provinces_without_findings": [], "comments": "", "job_complete": complete}
    data.update(extra)
    return {"type": "tool_use", "id": tool_id or f"toolu_{next(IDS)}", "name": d.TOOL_NAME, "input": data}


class FakeStream:
    def __init__(self, item):
        self.item = item

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if isinstance(self.item, BaseException):
            raise self.item
        return self.item


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def stream(self, **params):
        self.calls.append(copy.deepcopy(params))
        if not self.script:
            raise AssertionError("unexpected extra request")
        return FakeStream(self.script.pop(0))


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


def roles(params):
    return [m["role"] for m in params["messages"]]


def block_types(content):
    return [b["type"] if isinstance(b, dict) else b.type for b in content]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "discovery"
        self.raw = Path(self.tmp.name) / "raw"
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, script, **kwargs):
        client = FakeClient(script)
        runner = d.Runner(client, 1, out_dir=self.out, raw_dir=self.raw, log=self.logs.append, **kwargs)
        return runner, client

    def job(self, cap=24, index=0):
        return d.set_cap(d.round1_jobs()[index], cap)

    def cost_rows(self):
        with open(self.out / "cost_log.csv", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_paused_turn_continues_without_extra_message(self):
        script = [message("pause_turn", search(), searches=1, container="cntr_1"),
                  message("tool_use", [text("Found one."), record_call([candidate()], False, "toolu_a")], searches=1),
                  message("tool_use", [record_call([], True, "toolu_b")])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        first, second, third = client.messages.calls
        self.assertEqual(roles(first), ["user"])
        self.assertEqual(roles(second), ["user", "assistant"])
        self.assertEqual(second["container"], "cntr_1")
        self.assertEqual(roles(third), ["user", "assistant", "user"])
        self.assertEqual(block_types(third["messages"][1]["content"]),
                         ["server_tool_use", "web_search_tool_result", "text", "tool_use"])
        result = third["messages"][2]["content"][0]
        self.assertEqual((result["type"], result["tool_use_id"]), ("tool_result", "toolu_a"))
        self.assertNotIn("is_error", result)
        self.assertNotIn("Continue", json.dumps([m["content"] for m in third["messages"] if m["role"] == "user"]))
        records = d.read_jsonl(self.out / "round1.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["job_id"], "r1_a_sex_worker_led")
        self.assertEqual(records[0]["round"], 1)
        jobs = d.read_jsonl(self.out / "jobs_round1.jsonl")
        self.assertEqual([(j["status"], j["searches"], j["requests"]) for j in jobs], [("complete", 2, 3)])
        self.assertTrue((self.raw / "r1_a_sex_worker_led.json").exists())

    def test_invalid_input_returns_error_and_is_not_saved(self):
        script = [message("tool_use", [record_call([candidate(org_type="charity")], True, "toolu_a")]),
                  message("tool_use", [record_call([candidate()], True, "toolu_b")])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        result = client.messages.calls[1]["messages"][2]["content"][0]
        self.assertTrue(result["is_error"])
        payload = json.loads(result["content"])
        self.assertIn("INVALID_JSON", payload)
        self.assertTrue(any("org_type" in e for e in payload["errors"]))
        self.assertEqual(len(d.read_jsonl(self.out / "round1.jsonl")), 1)

    def test_check_input_rules(self):
        ok = record_call([candidate()], True)["input"]
        self.assertEqual(d.check_input(ok), [])
        bad = record_call([candidate(name_en="", name_th=""), candidate(website="example.org"),
                           candidate(evidence_url="", evidence_quote="a quote")], True)["input"]
        errors = d.check_input(bad)
        self.assertTrue(any("name_en or name_th" in e for e in errors))
        self.assertTrue(any("website" in e for e in errors))
        self.assertTrue(any("needs the URL" in e for e in errors))
        extra = record_call([dict(candidate(), phone="0812345678")], True)["input"]
        self.assertTrue(any("unknown field" in e for e in d.check_input(extra)))
        missing = record_call([], True)["input"]
        del missing["comments"]
        self.assertTrue(any("comments: missing" in e for e in d.check_input(missing)))

    def test_max_tokens_reissues_once_with_larger_limit(self):
        script = [message("max_tokens", [text("partial")]), message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        first, second = client.messages.calls
        self.assertEqual((first["max_tokens"], second["max_tokens"]), (d.MAX_TOKENS, d.MAX_TOKENS_RETRY))
        self.assertEqual(roles(second), ["user"])

    def test_max_tokens_twice_fails(self):
        script = [message("max_tokens", [text("partial")]), message("max_tokens", [text("partial")])]
        runner, _ = self.runner(script)
        self.assertEqual(runner.run_job(self.job())["status"], "failed")

    def test_parse_error_reissues_request(self):
        script = [ValueError("could not parse tool input"), message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(len(client.messages.calls), 2)
        self.assertEqual(summary["requests"], 1)

    def test_end_turn_without_record_sends_nudge_once(self):
        script = [message("end_turn", [text("Nothing found.")]), message("end_turn", [text("Still nothing.")])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "no_record")
        self.assertEqual(client.messages.calls[1]["messages"][-1], {"role": "user", "content": d.NUDGE})
        self.assertEqual(roles(client.messages.calls[1]), ["user", "assistant", "user"])

    def test_refusal_stops_job(self):
        runner, client = self.runner([message("refusal", [])])
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "refused")
        self.assertEqual(len(client.messages.calls), 1)
        self.assertFalse(runner.stop.is_set())

    def test_rerun_skips_only_jobs_that_would_buy_the_same_result(self):
        self.out.mkdir(parents=True)
        statuses = ["complete", "capped", "no_record", "refused", "stopped", "failed"]
        d.write_jsonl(self.out / "jobs_round1.jsonl", [{"job_id": f"job_{s}", "status": s} for s in statuses])
        runner, _ = self.runner([])
        self.assertEqual(runner.completed_jobs(), {"job_complete", "job_capped", "job_no_record", "job_refused"})

    def test_wrap_up_sent_once_after_search_limit(self):
        script = [message("tool_use", [record_call([candidate()], False)], searches=2),
                  message("tool_use", [record_call([], False)]),
                  message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job(cap=2))
        self.assertEqual(summary["status"], "complete")
        second, third = client.messages.calls[1], client.messages.calls[2]
        self.assertEqual(second["messages"][-1]["content"][-1], {"type": "text", "text": d.WRAP_UP})
        self.assertNotIn(d.WRAP_UP, json.dumps(third["messages"][-1]["content"]))

    def test_request_settings_and_tools_stay_the_same(self):
        script = [message("tool_use", [record_call([candidate()], False)], searches=2),
                  message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        runner.run_job(self.job())
        first, second = client.messages.calls
        self.assertEqual(first["tools"], second["tools"])
        self.assertEqual(first["system"], second["system"])
        self.assertEqual(first["cache_control"], {"type": "ephemeral"})
        self.assertEqual(first["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(first["thinking"], {"type": "adaptive"})
        self.assertEqual(first["tool_choice"], {"type": "auto"})
        self.assertEqual(first["output_config"], {"effort": "medium"})
        self.assertEqual(first["model"], "claude-sonnet-5-5")
        names = [t["name"] for t in first["tools"]]
        self.assertEqual(names, ["web_search", "record_candidates"])
        self.assertEqual(first["tools"][0]["type"], "web_search_20250305")
        self.assertTrue(first["tools"][1]["eager_input_streaming"])
        self.assertNotIn("strict", first["tools"][1])

    def test_round3_jobs_add_web_fetch(self):
        job = d.make_job("r3_leads", 3, d.LEADS_TASK)
        tools = d.tools_for(job)
        self.assertEqual([t["name"] for t in tools], ["web_search", "web_fetch", "record_candidates"])
        self.assertEqual(tools[1]["type"], "web_fetch_20250910")

    def test_search_tool_sends_no_location(self):
        # The API answers "Country code TH is not supported" when the search tool names Thailand as its location.
        for job in d.round1_jobs() + d.round2_jobs() + d.round3_jobs([]):
            self.assertEqual(set(d.tools_for(job)[0]), {"type", "name", "max_uses"})

    def test_limit_stops_run_and_skips_queued_jobs(self):
        script = [message("tool_use", [record_call([candidate()], False)], input_tokens=1_000_000)]
        runner, client = self.runner(script, limit=2.5)
        jobs = d.round1_jobs()[:2]
        for job in jobs:
            job["max_cost"] = 100
        summaries = {s["job_id"]: s for s in runner.run(jobs, workers=1)}
        self.assertEqual(summaries[jobs[0]["id"]]["status"], "stopped")
        self.assertEqual(summaries[jobs[1]["id"]]["status"], "skipped")
        self.assertEqual(len(client.messages.calls), 1)
        self.assertIn("spending limit", runner.stop_reason)
        persisted = [j["job_id"] for j in d.read_jsonl(self.out / "jobs_round1.jsonl")]
        self.assertEqual(persisted, [jobs[0]["id"]])
        self.assertEqual(len(d.read_jsonl(self.out / "round1.jsonl")), 1)
        rows = self.cost_rows()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(float(rows[0]["cost_usd"]), 2.005, places=3)

    def test_reserve_holds_room_for_requests_in_progress(self):
        runner, _ = self.runner([], limit=1.0)
        self.assertTrue(runner.reserve())
        self.assertTrue(runner.reserve())
        self.assertFalse(runner.reserve())
        self.assertTrue(runner.stop.is_set())
        self.assertEqual(runner.in_flight, 2)

    def test_run_stops_before_a_request_could_pass_the_limit(self):
        # each request costs $0.30, so a third would leave less than the $0.40 margin under the $0.90 limit
        script = [message("tool_use", [record_call([candidate()], False)], input_tokens=147_500),
                  message("tool_use", [record_call([], False)], input_tokens=147_500)]
        runner, client = self.runner(script, limit=0.9)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "stopped")
        self.assertEqual(len(client.messages.calls), 2)
        self.assertAlmostEqual(runner.spent, 0.60, places=4)
        self.assertEqual(runner.in_flight, 0)

    def test_margin_rises_to_the_dearest_request(self):
        runner, _ = self.runner([message("tool_use", [record_call([], True)], input_tokens=497_500)])
        runner.run_job(self.job())
        self.assertAlmostEqual(runner.margin, 1.0, places=4)

    def test_failed_request_releases_its_reservation(self):
        error = anthropic.AuthenticationError("invalid key", response=httpx2.Response(401, request=REQUEST), body=None)
        runner, _ = self.runner([error])
        runner.run_job(self.job())
        self.assertEqual((runner.in_flight, runner.spent), (0, 0.0))

    def test_job_cost_ceiling_caps_the_job_and_keeps_its_records(self):
        script = [message("tool_use", [record_call([candidate()], False)], input_tokens=297_500)]
        runner, client = self.runner(script)
        job = self.job()
        job["max_cost"] = 0.5
        summary = runner.run_job(job)
        self.assertEqual(summary["status"], "capped")
        self.assertIn("$0.60", summary["note"])
        self.assertEqual(len(client.messages.calls), 1)
        self.assertEqual(len(d.read_jsonl(self.out / "round1.jsonl")), 1)
        self.assertFalse(runner.stop.is_set())
        self.assertIn(job["id"], runner.completed_jobs())

    def test_searches_past_the_limit_cap_the_job(self):
        job = self.job(cap=2)
        self.assertEqual((job["max_uses"], job["max_searches"], job["max_cost"]), (2, 3, 0.2))
        runner, client = self.runner([message("tool_use", [record_call([candidate()], False)], searches=3)])
        summary = runner.run_job(job)
        self.assertEqual(summary["status"], "capped")
        self.assertIn("3 searches", summary["note"])
        self.assertEqual(len(client.messages.calls), 1)
        self.assertIn(job["id"], runner.completed_jobs())

    def test_one_request_may_use_the_whole_search_allowance(self):
        # The search tool's own limit message must mean that the job has no searches left.
        for job in d.round1_jobs() + d.round2_jobs() + d.round3_jobs([]):
            self.assertEqual(d.tools_for(job)[0]["max_uses"], job["cap"])

    def test_tool_result_says_how_many_searches_are_left(self):
        script = [message("tool_use", [record_call([candidate()], False)], searches=3),
                  message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        runner.run_job(self.job(cap=10))
        result = client.messages.calls[1]["messages"][-1]["content"][0]["content"]
        self.assertIn("3 of the 10 searches allowed in this job have run, so 7 are left", result)

    def test_log_line_counts_the_records_of_the_same_request(self):
        runner, _ = self.runner([message("tool_use", [record_call([candidate(), candidate(name_en="Other")], True)],
                                         searches=2)])
        runner.run_job(self.job())
        self.assertIn("request 1: tool_use, searches 2, recorded 2", self.logs[0])

    def test_cost_log_names_the_model(self):
        runner, _ = self.runner([message("tool_use", [record_call([], True)])])
        runner.run_job(self.job())
        rows = self.cost_rows()
        self.assertEqual(list(rows[0]), d.COST_FIELDS)
        self.assertEqual(rows[0]["model"], "claude-sonnet-5-5")
        self.assertAlmostEqual(float(rows[0]["cost_usd"]), 0.007, places=4)

    def test_overload_inside_stream_is_retried(self):
        error = anthropic.APIStatusError("overloaded", response=httpx2.Response(200, request=REQUEST),
                                         body={"type": "error", "error": {"type": "overloaded_error"}})
        script = [error, message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        with mock.patch.object(runner.stop, "wait", return_value=False) as wait:
            summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        wait.assert_called_once_with(30)
        self.assertEqual(len(client.messages.calls), 2)

    def test_overload_that_persists_fails_only_the_job(self):
        script = [anthropic.OverloadedError("overloaded", response=httpx2.Response(529, request=REQUEST), body=None)
                  for _ in range(d.MAX_OVERLOAD_WAITS + 1)]
        runner, _ = self.runner(script)
        with mock.patch.object(runner.stop, "wait", return_value=False):
            summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "failed")
        self.assertFalse(runner.stop.is_set())

    def test_authentication_error_halts_the_run(self):
        error = anthropic.AuthenticationError("invalid key", response=httpx2.Response(401, request=REQUEST), body=None)
        runner, _ = self.runner([error])
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "failed")
        self.assertTrue(runner.stop.is_set())

    def test_rejected_container_is_dropped(self):
        error = anthropic.BadRequestError("container cntr_1 has expired",
                                          response=httpx2.Response(400, request=REQUEST), body=None)
        script = [message("tool_use", [record_call([], False)], container="cntr_1"), error,
                  message("tool_use", [record_call([], True)])]
        runner, client = self.runner(script)
        summary = runner.run_job(self.job())
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(client.messages.calls[1]["container"], "cntr_1")
        self.assertNotIn("container", client.messages.calls[2])
        self.assertFalse(runner.stop.is_set())

    def test_rerun_replaces_the_job_records_and_lists_other_jobs(self):
        self.out.mkdir(parents=True)
        d.write_jsonl(self.out / "round1.jsonl", [
            {**candidate(name_en="Old Result", website="https://old.example"), "round": 1, "job_id": "r1_a_sex_worker_led"},
            {**candidate(name_en="Other Job Result", website="https://other.example"), "round": 1, "job_id": "r1_b_ngo_health"},
        ])
        script = [message("tool_use", [record_call([candidate(name_en="New Result", website="https://new.example")], True)])]
        runner, client = self.runner(script)
        runner.run_job(self.job())
        prompt = client.messages.calls[0]["messages"][0]["content"]
        self.assertIn("Other Job Result", prompt)
        self.assertNotIn("Old Result", prompt)
        names = sorted(r["name_en"] for r in d.read_jsonl(self.out / "round1.jsonl"))
        self.assertEqual(names, ["New Result", "Other Job Result"])

    def test_test_mode_writes_separate_files(self):
        runner, _ = self.runner([message("tool_use", [record_call([candidate()], True)])], test=True)
        runner.run_job(self.job(cap=3))
        self.assertTrue((self.out / "test_round1.jsonl").exists())
        self.assertFalse((self.out / "round1.jsonl").exists())
        self.assertTrue((self.raw / "test_r1_a_sex_worker_led.json").exists())


class MergeTests(unittest.TestCase):
    def test_url_keys(self):
        self.assertEqual(d.url_key("https://www.swingthailand.org/th/about"), "swingthailand.org")
        self.assertEqual(d.url_key("swingthailand.org"), "swingthailand.org")
        self.assertEqual(d.url_key("@SwingTH"), "line:@swingth")
        self.assertEqual(d.url_key("LINE ID @swingth"), "line:@swingth")
        self.assertEqual(d.url_key("https://line.me/R/ti/p/%40swingth"), "line:@swingth")
        self.assertEqual(d.url_key("https://m.facebook.com/swingthailand/posts/1"), "facebook.com/swingthailand")
        self.assertEqual(d.url_key("https://web.facebook.com/groups/123/permalink/9"), "facebook.com/groups/123")
        self.assertEqual(d.url_key("https://www.facebook.com/profile.php?id=42"), "facebook.com/profile.php?id=42")
        self.assertEqual(d.url_key("https://ddc.moph.go.th/odpc6/news.php"), "ddc.moph.go.th/odpc6")
        self.assertEqual(d.url_key("https://ddc.moph.go.th/th/"), "ddc.moph.go.th")
        self.assertEqual(d.url_key("https://fun.org/x"), "fun.org")
        self.assertEqual(d.url_key(""), "")

    def test_url_keys_on_platforms(self):
        cases = {
            "line.me/ti/p/@swingth": "line:@swingth",
            "https://page.line.me/swingth": "line:@swingth",
            "LINE ID: @swingth.": "line:@swingth",
            "info@example.org": "",
            "https://m.me/swingthailand": "facebook.com/swingthailand",
            "https://www.facebook.com/pg/swingthailand/about/": "facebook.com/swingthailand",
            "https://www.facebook.com/permalink.php?story_fbid=9&id=42": "facebook.com/profile.php?id=42",
            "https://www.facebook.com/share/p/AbC123/": "facebook.com/share/p/abc123",
            "https://www.facebook.com/pages/category/Nonprofit-Organization/Group-123/":
                "facebook.com/pages/category/nonprofit-organization/group-123",
            "https://www.facebook.com/p/Group-Name-100064/": "facebook.com/p/group-name-100064",
            "https://www.facebook.com/photo.php?fbid=1": "",
            "https://www.facebook.com/events/123/": "",
            "https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.org": "",
            "https://docs.google.com/forms/d/e/abc/viewform": "docs.google.com/forms/d/e/abc/viewform",
            "https://drive.google.com/open?id=XYZ": "drive.google.com/open?id=XYZ",
            "https://forms.gle/AbC": "forms.gle/abc",
            "https://sites.google.com/view/swing/home": "sites.google.com/view/swing",
            "https://www.instagram.com/swingthailand/": "instagram.com/swingthailand",
            "https://www.instagram.com/p/xyz/": "",
            "https://www.youtube.com/watch?v=1": "",
            "https://www.youtube.com/@swingthailand/videos": "youtube.com/@swingthailand",
            "https://twitter.com/swing/status/1": "x.com/swing",
            "https://www.tiktok.com/@swing/video/1": "tiktok.com/@swing",
            "https://vm.tiktok.com/AbC/": "vm.tiktok.com/abc",
            "https://th.linkedin.com/company/raks-thai/": "linkedin.com/company/raks-thai",
            "https://www.linkedin.com/posts/abc": "",
            "https://[broken": "",
        }
        for url, key in cases.items():
            self.assertEqual(d.url_key(url), key, url)

    def test_is_social(self):
        self.assertTrue(d.is_social("@swingth"))
        self.assertTrue(d.is_social("https://www.facebook.com/photo.php?fbid=1"))
        self.assertTrue(d.is_social("https://lin.ee/AbC"))
        self.assertFalse(d.is_social("https://swingthailand.org"))
        self.assertFalse(d.is_social("https://docs.google.com/forms/d/e/abc/viewform"))
        self.assertFalse(d.is_social(""))

    def test_shared_platforms_do_not_join_organisations(self):
        records = [candidate(name_en="Group A", website="", facebook_or_line="https://www.facebook.com/photo.php?fbid=1"),
                   candidate(name_en="Group B", website="", facebook_or_line="https://www.facebook.com/photo.php?fbid=2"),
                   candidate(name_en="Group C", website="https://docs.google.com/forms/d/e/aaa/viewform"),
                   candidate(name_en="Group D", website="https://docs.google.com/forms/d/e/bbb/viewform"),
                   candidate(name_en="Group E", website="https://www.facebook.com/share/111/"),
                   candidate(name_en="Group F", website="https://www.facebook.com/share/222/")]
        self.assertEqual(len(d.build_orgs(records)), 6)

    def test_lead_matching_avoids_short_partial_names(self):
        self.assertFalse(d.lead_found(["sistersfoundation", "มูลนิธิซิสเตอร์"], {d.norm_name("Good Shepherd Sisters")}))
        self.assertTrue(d.lead_found(["sistersfoundation"], {d.norm_name("Sisters Foundation Pattaya")}))
        self.assertTrue(d.lead_found(["swing"], {d.norm_name("SWING")}))
        self.assertFalse(d.lead_found(["swing"], {d.norm_name("Swing Bar")}))
        self.assertTrue(d.lead_found(["มูลนิธิเอ็มพลัส"], {d.norm_name("มูลนิธิเอ็มพลัส เชียงใหม่")}))

    def test_merge_groups_records_into_organisations_and_sites(self):
        records = [
            {**candidate(name_en="SWING", website="https://www.swingthailand.org/"), "round": 1, "job_id": "r1_a"},
            {**candidate(name_en="Service Workers in Group Foundation", website="http://swingthailand.org/th/about",
                         facebook_or_line="https://www.facebook.com/swingthailand/", services_mentioned=["prep"],
                         sex_worker_led="yes"), "round": 2, "job_id": "r2_bkk"},
            {**candidate(name_en="SWING Pattaya", website="", facebook_or_line="https://m.facebook.com/swingthailand",
                         province_codes=["TH-20"], city="Pattaya"), "round": 2, "job_id": "r2_chb"},
            {**candidate(name_en="Service Workers in Group Foundation", website="", province_codes=["TH-20"],
                         city="Pattaya", evidence_quote="Another quote."), "round": 3, "job_id": "r3_social"},
            {**candidate(name_en="Other Group", website="https://other.example", province_codes=["TH-50"],
                         city="Chiang Mai", sex_worker_mention="unclear"), "round": 2, "job_id": "r2_cnx"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out_csv, counts_csv = Path(tmp) / "candidates.csv", Path(tmp) / "province_counts.csv"
            rows = d.merge(records, out_csv, counts_csv, log=lambda *_: None)
            self.assertEqual(len({r["org_id"] for r in rows}), 2)
            self.assertEqual(len(rows), 3)
            bangkok = next(r for r in rows if r["province_codes"] == "TH-10")
            self.assertEqual(bangkok["n_records"], 2)
            self.assertEqual(bangkok["found_in_rounds"], "1; 2")
            self.assertEqual(bangkok["services_mentioned"], "hiv_testing; prep")
            self.assertEqual(bangkok["sex_worker_led"], "yes")
            pattaya = next(r for r in rows if r["province_codes"] == "TH-20")
            self.assertEqual(pattaya["n_records"], 2)
            self.assertEqual(pattaya["org_id"], bangkok["org_id"])
            self.assertNotEqual(pattaya["site_id"], bangkok["site_id"])
            with open(out_csv, encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 3)
            with open(counts_csv, encoding="utf-8-sig") as f:
                counts = {r["code"]: r for r in csv.DictReader(f)}
            self.assertEqual(len(counts), 77)
            self.assertEqual(counts["TH-10"]["candidates"], "1")
            self.assertEqual(counts["TH-50"]["candidates_sex_worker_named"], "0")
            self.assertEqual(counts["TH-96"]["candidates"], "0")

    def test_record_without_city_joins_the_only_site_in_its_provinces(self):
        mplus = dict(name_en="Mplus Foundation - Lampang", website="https://www.mplusthailand.com/en/",
                     province_codes=["TH-52"])
        records = [candidate(**mplus, city="Mueang Lampang", sex_worker_mention="unclear"),
                   candidate(**mplus, city="")]
        rows = d.site_rows(d.build_orgs(records))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["city"], rows[0]["sex_worker_mention"], rows[0]["n_records"]),
                         ("Mueang Lampang", "yes", 2))
        branches = [candidate(**mplus, city="Mueang Lampang"), candidate(**mplus, city="Ko Kha"), candidate(**mplus, city="")]
        self.assertEqual(len(d.site_rows(d.build_orgs(branches))), 3)
        logged = []
        with tempfile.TemporaryDirectory() as tmp:
            d.merge(branches, Path(tmp) / "c.csv", Path(tmp) / "p.csv", log=logged.append)
        self.assertIn("(Ko Kha)", logged[-1])
        self.assertIn("(no city)", logged[-1])

    def test_round3_jobs_follow_up_on_earlier_rounds(self):
        records = [
            candidate(name_en="SWING", website="https://swingthailand.org",
                      partner_list_url="https://swingthailand.org/partners"),
            candidate(name_en="Local Group", website="", facebook_or_line="https://facebook.com/localgroup",
                      province_codes=["TH-20"], city="Pattaya"),
        ]
        jobs = d.round3_jobs(records)
        ids = [j["id"] for j in jobs]
        self.assertEqual(ids, ["r3_leads", "r3_snowball_1"] + [f"r3_gap_{i}" for i in range(1, 26)] + ["r3_social"])
        self.assertTrue(all(j["fetch"] for j in jobs))
        self.assertTrue(all(j["cap"] == 6 and j["max_uses"] == 6 for j in jobs))
        gaps = {c for j in jobs if j["id"].startswith("r3_gap") for c in j["provinces"]}
        self.assertEqual(len(gaps), 75)
        self.assertFalse({"TH-10", "TH-20"} & gaps)
        pages = next(j for j in jobs if j["id"] == "r3_snowball_1")["details"].splitlines()[1:]
        self.assertEqual(pages, [f"- {d.CLINIC_LISTS[0]}", "- https://swingthailand.org/partners"])
        leads = next(j for j in jobs if j["id"] == "r3_leads")["details"]
        self.assertNotIn("SWING", leads)
        self.assertIn("Empower Foundation", leads)

    def test_round3_reads_the_clinic_list_first_and_at_most_eight_pages(self):
        records = [candidate(name_en=f"Group {i}", website=f"https://group{i}.example",
                             partner_list_url=f"https://group{i}.example/partners") for i in range(12)]
        records.append(candidate(name_en="Page Only Group", website="", facebook_or_line="https://facebook.com/pageonly"))
        jobs = d.round3_jobs(records)
        ids = [j["id"] for j in jobs]
        self.assertEqual(ids[:3], ["r3_leads", "r3_snowball_1", "r3_snowball_2"])
        self.assertEqual(ids[-1], "r3_social")
        pages = [line for j in jobs if j["id"].startswith("r3_snowball") for line in j["details"].splitlines()[1:]]
        self.assertEqual(len(pages), d.MAX_SNOWBALL_PAGES)
        self.assertEqual(pages[0], f"- {d.CLINIC_LISTS[0]}")

    def test_gap_jobs_search_each_province_twice_in_jobs_of_three(self):
        jobs = d.gap_jobs([])
        self.assertEqual(sorted(c for j in jobs for c in j["provinces"]), sorted(d.PROVINCE_CODES))
        self.assertTrue(all(2 <= len(j["provinces"]) <= d.GAP_PROVINCES_PER_JOB for j in jobs))
        self.assertTrue(all(j["cap"] == j["max_uses"] == 2 * len(j["provinces"]) for j in jobs))
        self.assertEqual(sum(j["cap"] for j in jobs), 2 * 77)

    def test_province_counts_as_found_only_when_a_source_names_sex_workers(self):
        records = [candidate(name_en="Clear Group", province_codes=["TH-50"], sex_worker_mention="yes"),
                   candidate(name_en="Unclear Group", province_codes=["TH-21"], sex_worker_mention="unclear",
                             website="https://unclear.example"),
                   candidate(name_en="Branch Group - Chiang Mai", province_codes=["TH-50"], website="https://branch.example"),
                   candidate(name_en="Branch Group - Chiang Mai", province_codes=["TH-50"], website="https://branch.example"),
                   candidate(name_en="Branch Group - Lampang", province_codes=["TH-52"], sex_worker_mention="unclear",
                             website="https://branch.example")]
        jobs = d.gap_jobs(records)
        gaps = {c for j in jobs for c in j["provinces"]}
        self.assertNotIn("TH-50", gaps)
        self.assertIn("TH-21", gaps)
        job = next(j for j in jobs if "TH-21" in j["provinces"])
        self.assertIn(d.GAP_RECHECK, job["details"])
        self.assertIn("- Unclear Group [TH-21]", job["details"])
        lampang = next(j for j in jobs if "TH-52" in j["provinces"])["details"]
        self.assertIn("- Branch Group - Lampang [TH-52]", lampang)
        self.assertNotIn("Chiang Mai [TH-52]", lampang)
        other = next(j for j in jobs if "TH-21" not in j["provinces"])
        self.assertNotIn(d.GAP_RECHECK, other["details"])

    def test_prompt_asks_for_every_search_and_avoids_the_bare_term(self):
        self.assertNotIn("costs money", d.SYSTEM)
        self.assertIn("Use all of them", d.SYSTEM)
        self.assertIn("never name more than one province in a query", d.SYSTEM)
        self.assertNotIn("พนักงานบริการ", d.TAXONOMY["search_terms"]["sex_workers_th"])
        self.assertNotIn("พนักงานบริการ,", d.GAP_TASK)


class ConfigTests(unittest.TestCase):
    def test_provinces(self):
        self.assertEqual(len(d.PROVINCES), 77)
        self.assertEqual(len(set(d.PROVINCE_CODES)), 77)
        self.assertEqual(len({p["cluster"] for p in d.PROVINCES}), 24)
        self.assertEqual(Counter(p["region"] for p in d.PROVINCES),
                         Counter({"Northeast": 20, "Central": 22, "South": 14, "North": 9, "East": 7, "West": 5}))
        for p in d.PROVINCES:
            self.assertTrue(p["name_th"] and p["towns_en"] and p["towns_th"], p["code"])

    def test_round_sizes(self):
        round1 = d.round1_jobs()
        self.assertEqual(len(round1), 5)
        self.assertEqual(sum(j["cap"] for j in round1), 50)
        round2 = d.round2_jobs()
        self.assertEqual(len(round2), 24)
        self.assertEqual(sum(j["cap"] for j in round2), 152)
        self.assertEqual({j["cluster"] for j in round2 if j["cap"] == 8}, d.BIG_CLUSTERS)
        self.assertEqual(sorted(c for j in round2 for c in j["provinces"]), sorted(d.PROVINCE_CODES))
        self.assertEqual(len(d.round3_jobs([])), 28)
        self.assertTrue(all(j["cap"] == 3 for j in d.build_jobs(1, test=True)))

    def test_taxonomy_matches_tool_schema(self):
        schema = d.RECORD_SCHEMA["properties"]["candidates"]["items"]
        self.assertEqual(schema["properties"]["services_mentioned"]["items"]["enum"], d.SERVICE_IDS)
        self.assertEqual(len(d.SERVICE_IDS), 19)
        self.assertEqual(sum(s["core"] for s in d.TAXONOMY["service_types"]), 9)

        def walk(node):
            if node.get("type") == "object":
                self.assertIs(node["additionalProperties"], False)
                self.assertEqual(sorted(node["required"]), sorted(node["properties"]))
                for sub in node["properties"].values():
                    walk(sub)
            if node.get("type") == "array":
                walk(node["items"])
            for key in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
                self.assertNotIn(key, node)
        walk(d.RECORD_SCHEMA)

    def test_dry_runs_need_no_key(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        for round_no in ("1", "2", "3"):
            done = subprocess.run([sys.executable, str(ROOT / "scripts" / "discover.py"), "--round", round_no,
                                   "--dry-run"], capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("No API calls were made.", done.stdout)


class EnvTests(unittest.TestCase):
    def test_env_file_fills_an_empty_shell_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("﻿export ANTHROPIC_API_KEY='test-key'\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
                d.load_env(path)
                self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "test-key")
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "shell-key"}):
                d.load_env(path)
                self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "shell-key")

    def test_empty_key_message_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(d, "ROOT", Path(tmp)), \
                    mock.patch.object(d, "DISCOVERY", Path(tmp) / "discovery"), \
                    mock.patch.object(d, "load_env", lambda *args, **kwargs: None):
                with self.assertRaises(SystemExit) as caught:
                    d.run_round(mock.Mock(round=1, test=True, share=13.0, budget=None), [])
            self.assertIn("The key in .env is empty", str(caught.exception.code))


class SpendingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_log(self, rows):
        with open(self.dir / "cost_log.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=d.COST_FIELDS)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, d.now_iso() if k == "timestamp" else 0) for k in d.COST_FIELDS})

    def test_request_cost_for_each_model(self):
        usage = anthropic.types.Usage.model_validate(
            {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_creation_input_tokens": 100_000,
             "cache_read_input_tokens": 1_000_000, "server_tool_use": {"web_search_requests": 10, "web_fetch_requests": 2}})
        cost, searches, fetches = d.request_cost(usage, "claude-sonnet-5-5")
        self.assertAlmostEqual(cost, 3.55, places=6)
        self.assertEqual((searches, fetches), (10, 2))
        self.assertAlmostEqual(d.request_cost(usage, "claude-opus-5-5")[0], 6.80, places=6)

    def test_logged_spend_and_limit(self):
        self.assertEqual(d.logged_spend(self.dir / "cost_log.csv"), 0)
        self.write_log([{"cost_usd": "0.5000", "test": 1}, {"cost_usd": "0.2500"}])
        self.assertAlmostEqual(d.logged_spend(self.dir / "cost_log.csv"), 0.75)
        self.assertEqual(d.spending_limit(13, 2), 11)
        self.assertEqual(d.spending_limit(13, 2, budget=5), 5)
        self.assertEqual(d.spending_limit(13, 2, budget=5, test=True), d.TEST_LIMIT)
        self.assertAlmostEqual(d.spending_limit(13, 12.5, test=True), 0.5)

    def test_estimate_uses_only_requests_with_the_same_model(self):
        jobs = d.round1_jobs()
        log = self.dir / "cost_log.csv"
        self.write_log([{"model": "claude-opus-5-5", "web_searches": 10, "cost_usd": "5.0000"}])
        self.assertIn("rough range", d.estimate(jobs, "claude-sonnet-5-5", log))
        self.write_log([{"model": "claude-opus-5-5", "web_searches": 10, "cost_usd": "5.0000"},
                        {"model": "claude-sonnet-5-5", "web_searches": 10, "cost_usd": "1.0000"}])
        text = d.estimate(jobs, "claude-sonnet-5-5", log)
        self.assertIn("About $5.00 for 5 jobs with up to 50 searches", text)
        self.assertIn("$0.100 for each search", text)
        self.assertIn("may not run", d.estimate(jobs, "claude-sonnet-5-5", log, left=3.0))

    def test_estimate_ignores_requests_before_basic_search(self):
        log = self.dir / "cost_log.csv"
        self.write_log([{"timestamp": "2026-10-04T02:48:24+00:00", "model": d.MODEL, "web_searches": 5, "cost_usd": "0.1145"},
                        {"timestamp": "2026-10-04T03:07:14+00:00", "model": d.MODEL, "web_searches": 9, "cost_usd": "0.3665"}])
        text = d.estimate(d.round1_jobs()[:1], d.MODEL, log)
        self.assertIn("$0.041 for each search", text)
        self.assertIn("from 1 logged request costing $0.37", text)
        self.assertAlmostEqual(d.logged_spend(log), 0.481)

    def test_command_does_not_start_once_the_share_is_spent(self):
        self.write_log([{"model": d.MODEL, "cost_usd": "12.7000"}])
        with mock.patch.object(d, "DISCOVERY", self.dir), mock.patch.object(d, "load_env") as load_env:
            with self.assertRaises(SystemExit) as caught:
                d.main(["--round", "1"])
            self.assertIn("Not started", str(caught.exception.code))
            self.assertIn("--share 15.00", str(caught.exception.code))
            with self.assertRaises(SystemExit) as caught:
                d.main(["--round", "1", "--share", "20", "--budget", "0.3"])
            self.assertIn("less than one request can cost", str(caught.exception.code))
        load_env.assert_not_called()

    def test_round3_waits_for_rounds_1_and_2(self):
        with mock.patch.object(d, "DISCOVERY", self.dir), mock.patch.object(d, "load_env") as load_env:
            with self.assertRaises(SystemExit) as caught:
                d.main(["--round", "3"])
            self.assertIn("rounds 1 and 2 have 29 unfinished jobs", str(caught.exception.code))
            self.assertIn("--round 1 and --round 2 commands", str(caught.exception.code))
            d.write_jsonl(self.dir / "jobs_round1.jsonl", [{"job_id": j["id"], "status": "complete"}
                                                           for j in d.round1_jobs()])
            d.write_jsonl(self.dir / "jobs_round2.jsonl", [{"job_id": j["id"], "status": "failed" if i == 0 else "capped"}
                                                           for i, j in enumerate(d.round2_jobs())])
            first = d.round2_jobs()[0]["id"]
            with self.assertRaises(SystemExit) as caught:
                d.main(["--round", "3"])
            self.assertIn(f"1 unfinished job ({first})", str(caught.exception.code))
            self.assertIn("the --round 2 command again", str(caught.exception.code))
            d.write_jsonl(self.dir / "jobs_round2.jsonl", [{"job_id": first, "status": "no_record"}])
            with self.assertRaises(SystemExit) as caught:  # past the round 3 check, stopped by the budget check
                d.main(["--round", "3", "--budget", "0.3"])
            self.assertIn("less than one request can cost", str(caught.exception.code))
        load_env.assert_not_called()


if __name__ == "__main__":
    unittest.main()
