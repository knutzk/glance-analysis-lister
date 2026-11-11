# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Coverage comments use validated numbers and server-verified PR identities."""

import io
import json
import unittest
import zipfile
from copy import deepcopy
from urllib.request import Request

from scripts.coverage_summary import (
    LIMIT,
    MARKER,
    SafeRedirect,
    Totals,
    publish,
    read_totals,
)

HEAD = "a" * 40
BASE = "b" * 40


def archive(lines=(90, 100), branches=(30, 40), **extra):
    stream = io.BytesIO()
    report = {
        "meta": {"branch_coverage": True},
        "totals": {
            "covered_lines": lines[0],
            "num_statements": lines[1],
            "covered_branches": branches[0],
            "num_branches": branches[1],
            "percent_covered": "@everyone forged percentage",
        },
    }
    report.update(extra)
    with zipfile.ZipFile(stream, "w") as zipped:
        zipped.writestr("coverage.json", json.dumps(report))
        zipped.writestr(
            "../../publisher.py", "raise RuntimeError('must never execute')"
        )
    return stream.getvalue()


class FakeGitHub:
    repository = "invented/package"
    web = "https://github.com"

    def __init__(self):
        self.run = {
            "id": 20,
            "workflow_id": 7,
            "event": "pull_request",
            "status": "completed",
            "head_sha": HEAD,
            "head_branch": "fix",
            "run_attempt": 1,
            "repository": {"full_name": self.repository},
            "head_repository": {"id": 2, "owner": {"login": "invented-fork"}},
            "pull_requests": [],
        }
        self.pr = {
            "number": 12,
            "state": "open",
            "head": {"sha": HEAD, "ref": "fix", "repo": {"id": 2}},
            "base": {
                "sha": BASE,
                "ref": "main",
                "repo": {"full_name": self.repository},
            },
        }
        self.associated = [deepcopy(self.pr)]
        self.latest = [self.run]
        self.baselines = [
            {
                "id": 10,
                "run_attempt": 1,
                "head_sha": BASE,
                "head_branch": "main",
                "event": "push",
                "conclusion": "success",
            }
        ]
        self.artifacts = {
            20: [{"id": 200, "name": "python-coverage", "expired": False}],
            10: [{"id": 100, "name": "python-coverage", "expired": False}],
        }
        self.archives = {
            200: archive(),
            100: archive(lines=(85, 100), branches=(32, 40)),
        }
        self.comments = []
        self.writes = []
        self.failed = False
        self.stale = False
        self.pr_reads = 0

    def request(self, path, *, method="GET", body=None, binary=False):
        if method != "GET":
            self.writes.append((method, path, body["body"]))
            return {}
        if path == "actions/workflows/ci.yml":
            return {"id": 7}
        if path == "actions/runs/20":
            return self.run
        if path == "pulls/12":
            self.pr_reads += 1
            pr = deepcopy(self.pr)
            if self.stale and self.pr_reads > 1:
                pr["head"]["sha"] = "c" * 40
            return pr
        if path.startswith("actions/artifacts/"):
            assert binary
            return self.archives[int(path.split("/")[2])]
        raise AssertionError(path)

    def pages(self, path, key=None):
        if path == "pulls?state=open&base=main&head=invented-fork%3Afix":
            return iter(self.associated)
        if path.startswith("actions/workflows/7/runs?event=pull_request"):
            return iter(self.latest)
        if path.startswith("actions/workflows/7/runs?event=push"):
            assert f"head_sha={BASE}" in path and "branch=main" in path
            return iter(self.baselines)
        if path.endswith("/artifacts"):
            return iter(self.artifacts[int(path.split("/")[2])])
        if path.endswith("/jobs"):
            outcome = (
                "failure"
                if self.failed and path.startswith("actions/runs/20/")
                else "success"
            )
            return iter(
                [
                    {
                        "name": "checks",
                        "steps": [
                            {
                                "name": "Run offline regression tests",
                                "conclusion": outcome,
                            },
                            {
                                "name": "Report offline Python coverage",
                                "conclusion": "success",
                            },
                        ],
                    }
                ]
            )
        if path == "issues/12/comments":
            return iter(self.comments)
        raise AssertionError(path)


class CoverageSummaryTests(unittest.TestCase):
    def test_reports_counts_deltas_and_artifact_link_for_fork_with_empty_run_prs(self):
        api = FakeGitHub()
        publish(api, 20)
        method, path, body = api.writes[0]
        self.assertEqual((method, path), ("POST", "issues/12/comments"))
        self.assertIn("90.00% (90/100) | 85.00% (85/100) | +5.00 pp", body)
        self.assertIn("75.00% (30/40) | 80.00% (32/40) | -5.00 pp", body)
        self.assertIn("actions/runs/20/artifacts/200", body)
        self.assertIn(BASE[:12], body)
        self.assertNotIn("@everyone", body)

    def test_updates_only_our_bot_comment_and_dry_run_never_writes(self):
        for login, kind, expected in [
            ("invented-user", "User", "POST"),
            ("another-bot[bot]", "Bot", "POST"),
            ("github-actions[bot]", "Bot", "PATCH"),
        ]:
            with self.subTest(login=login):
                api = FakeGitHub()
                api.comments = [
                    {"id": 55, "user": {"login": login, "type": kind}, "body": MARKER}
                ]
                self.assertIn("Python coverage", publish(api, 20, dry_run=True))
                self.assertEqual(api.writes, [])
                publish(api, 20)
                self.assertEqual(api.writes[0][0], expected)
                if expected == "PATCH":
                    self.assertEqual(api.writes[0][1], "issues/comments/55")

    def test_ignores_wrong_workflow_event_repository_and_unfinished_runs(self):
        for key, value in [
            ("workflow_id", 99),
            ("event", "push"),
            ("status", "in_progress"),
            ("repository", {"full_name": "other/project"}),
        ]:
            with self.subTest(key=key):
                api = FakeGitHub()
                api.run[key] = value
                self.assertIn("Skipped", publish(api, 20))
                self.assertEqual(api.writes, [])

    def test_rejects_wrong_pr_head_repository_base_closed_and_ambiguous_prs(self):
        for change in [
            lambda pr: pr["head"].update(sha="c" * 40),
            lambda pr: pr["head"].update(repo={"id": 999}),
            lambda pr: pr["head"].update(repo=None),
            lambda pr: pr["base"].update(ref="other"),
            lambda pr: pr.update(state="closed"),
        ]:
            api = FakeGitHub()
            change(api.associated[0])
            self.assertIn("Skipped", publish(api, 20))
            self.assertFalse(api.writes)
        api = FakeGitHub()
        api.associated.append(deepcopy(api.pr))
        self.assertIn("Skipped", publish(api, 20))

    def test_does_not_overwrite_newer_runs_or_heads(self):
        for newer in [{"id": 21, "run_attempt": 1}, {"id": 20, "run_attempt": 2}]:
            api = FakeGitHub()
            api.latest.append(newer)
            self.assertIn("newer", publish(api, 20))
            self.assertFalse(api.writes)
        api = FakeGitHub()
        api.stale = True
        self.assertIn("PR changed", publish(api, 20))
        self.assertFalse(api.writes)

    def test_missing_expired_invalid_and_wrong_sha_baseline_are_not_zero(self):
        for scenario in ("missing", "expired", "invalid", "wrong-sha"):
            with self.subTest(scenario=scenario):
                api = FakeGitHub()
                if scenario == "missing":
                    api.baselines = []
                elif scenario == "expired":
                    api.artifacts[10][0]["expired"] = True
                elif scenario == "invalid":
                    api.archives[100] = b"invalid zip"
                else:
                    api.baselines[0]["head_sha"] = "c" * 40
                body = publish(api, 20, dry_run=True)
                self.assertIn("90.00% (90/100) | N/A | N/A", body)
                self.assertIn("No older baseline was substituted", body)

    def test_failed_tests_and_missing_pr_report_do_not_claim_improvement(self):
        for missing in (False, True):
            api = FakeGitHub()
            api.failed = True
            if missing:
                api.artifacts[20] = []
            body = publish(api, 20, dry_run=True)
            self.assertIn("Incomplete / unavailable", body)
            self.assertNotIn("+5.00 pp", body)
            self.assertNotIn("-5.00 pp", body)
            self.assertIn("no change is calculated", body)

    def test_zero_denominators_are_not_invented_percentages(self):
        api = FakeGitHub()
        api.archives[200] = archive(lines=(0, 0), branches=(0, 0))
        body = publish(api, 20, dry_run=True)
        self.assertIn("N/A (0/0)", body)
        self.assertNotIn(" pp |", body)

    def test_rejects_bad_counts_missing_branch_data_and_duplicate_json(self):
        for counts in [(True, 100), (101, 100), (-1, 100), (1.5, 100), (1, 10**10)]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                read_totals(archive(lines=counts))
        with self.assertRaises(ValueError):
            read_totals(archive(meta={"branch_coverage": False}))
        stream = io.BytesIO(archive())
        # Deliberately duplicated entries must never select an arbitrary report.
        with zipfile.ZipFile(stream, "a") as zipped, self.assertWarns(UserWarning):
            zipped.writestr("coverage.json", "{}")
        with self.assertRaises(ValueError):
            read_totals(stream.getvalue())

    def test_never_extracts_archive_members_and_bounds_json(self):
        self.assertEqual(read_totals(archive()), Totals((90, 100), (30, 40)))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("coverage.json", " " * (LIMIT + 1))
        with self.assertRaises(ValueError):
            read_totals(stream.getvalue())

    def test_redirect_strips_api_token_and_rejects_http(self):
        request = Request(
            "https://api.github.com/artifact", headers={"Authorization": "Bearer fake"}
        )
        handler = SafeRedirect()
        redirected = handler.redirect_request(
            request, None, 302, "Found", {}, "https://storage.example/file"
        )
        self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(ValueError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://storage.example/file"
            )


if __name__ == "__main__":
    unittest.main()
