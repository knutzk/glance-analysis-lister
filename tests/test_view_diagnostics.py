# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Diagnostic causes, severity, page inclusion and user-visible explanations."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from view_fixtures import analysis, publication, snapshot

from analysis_lister.views.build import render_group
from analysis_lister.views.diagnostics import diagnostic_entry, group_diagnostics
from analysis_lister.views.profiles import GroupProfile


class DiagnosticReportTests(unittest.TestCase):
    def test_review_and_relationship_issues_are_listed_and_logged(self):
        uncertain = analysis(1, status="Phase 0 Finished")
        linked = analysis(2)
        linked["relatedPublications"] = [
            {"type": "Paper", "referenceCode": "DEMO-2099-99"}
        ]
        unrelated = analysis(3, group="OTHER", status="Phase 0 Finished")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(snapshot(uncertain, linked, unrelated)))
            with self.assertLogs(
                "analysis_lister.views.build", level="WARNING"
            ) as logs:
                counts = render_group(source, root / "pages", GroupProfile("DEMO"))
            report = json.loads((root / "pages/view-report.json").read_text())
        self.assertEqual(counts["analyses_needing_review"], 1)
        self.assertEqual(counts["records_with_diagnostics"], 2)
        self.assertEqual(len(report["analyses_needing_review"]), 1)
        self.assertEqual(len(report["records_with_diagnostics"]), 2)
        self.assertEqual(
            report["analyses_needing_review"][0]["reference"],
            uncertain["referenceCode"],
        )
        self.assertEqual(
            {row["reference"] for row in report["records_with_diagnostics"]},
            {uncertain["referenceCode"], linked["referenceCode"]},
        )
        messages = "\n".join(logs.output)
        self.assertIn(
            "Uncertain lifecycle state: 1 issue(s) across 1 record(s)", messages
        )
        self.assertIn("Excluded from ongoing analyses", messages)
        self.assertIn(
            "Unresolved publication links: 1 issue(s) across 1 record(s)", messages
        )
        self.assertIn("Included in ongoing analyses", messages)
        self.assertIn(
            "Effect: Publication state and milestones are unavailable", messages
        )
        self.assertEqual(counts["warning_issues"], 2)
        self.assertEqual(counts["informational_issues"], 0)
        self.assertEqual(
            {group["code"] for group in report["diagnostic_groups"]},
            {"unknown_state", "missing_publication"},
        )
        self.assertIn(uncertain["referenceCode"], messages)
        self.assertIn(
            "source does not establish an ongoing or completed state", messages
        )
        self.assertIn("analyses/" + linked["referenceCode"], messages)
        self.assertIn("unresolved publication link (Paper: DEMO-2099-99)", messages)
        self.assertNotIn(unrelated["referenceCode"], messages)

    def test_clean_group_has_empty_attention_lists(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(snapshot(analysis(1))))
            with self.assertNoLogs("analysis_lister.views.build", level="WARNING"):
                render_group(source, root / "pages", GroupProfile("DEMO"))
            report = json.loads((root / "pages/view-report.json").read_text())
        self.assertEqual(report["analyses_needing_review"], [])
        self.assertEqual(report["records_with_diagnostics"], [])
        self.assertEqual(report["diagnostic_groups"], [])
        self.assertEqual(report["counts"]["warning_issues"], 0)

    def test_publication_diagnostic_identifies_unresolved_analysis(self):
        entry = diagnostic_entry(
            {
                "resource": "papers",
                "reference": "DEMO-2099-01",
                "state": {"value": "published"},
                "relatedAnalysis": {
                    "type": "Analysis",
                    "referenceCode": "ANA-DEMO-2099-99",
                },
                "relationship_issue": "unresolved relatedAnalysis",
            }
        )
        self.assertEqual(
            entry["reasons"],
            ["unresolved relatedAnalysis (Analysis: ANA-DEMO-2099-99)"],
        )

    def test_one_way_relationship_is_informational_and_does_not_exclude_analysis(self):
        record = analysis(1)
        paper = publication(1, status="Phase 1 Active", date=None)
        record["relatedPublications"] = [
            {"type": "Paper", "referenceCode": paper["referenceCode"]}
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(snapshot(record, papers=(paper,))))
            with self.assertLogs("analysis_lister.views.build", level="INFO") as logs:
                counts = render_group(source, root / "pages", GroupProfile("DEMO"))
            report = json.loads((root / "pages/view-report.json").read_text())
        self.assertEqual(counts["warning_issues"], 0)
        self.assertEqual(counts["informational_issues"], 1)
        self.assertEqual(counts["ongoing_analyses"], 1)
        self.assertTrue(all(record.levelname == "INFO" for record in logs.records))
        group = report["diagnostic_groups"][0]
        self.assertEqual(group["code"], "one_way_publication")
        self.assertEqual(
            group["entries"][0]["placement"], "Included in ongoing analyses"
        )
        self.assertIn("reciprocal relatedAnalysis", group["entries"][0]["effect"])

    def test_multiple_issues_count_separately_from_records(self):
        trace = {
            "resource": "analyses",
            "reference": "ANA-DEMO-2099-01",
            "state": {"value": "phase0"},
            "inclusion": {"value": True},
            "relationship_issues": [
                {
                    "reason": "unresolved publication link",
                    "link": {
                        "type": "Paper",
                        "referenceCode": f"DEMO-2099-{number:02}",
                    },
                }
                for number in (2, 3)
            ],
        }
        groups = group_diagnostics([diagnostic_entry(trace)])
        self.assertEqual(groups[0]["issue_count"], 2)
        self.assertEqual(groups[0]["record_count"], 1)
        self.assertEqual(len(groups[0]["entries"]), 2)

    def test_published_paper_with_missing_analysis_stays_in_archive(self):
        paper = publication(1, related="ANA-DEMO-2099-88")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(snapshot(analysis(1), papers=(paper,))))
            with self.assertLogs("analysis_lister.views.build", level="WARNING"):
                counts = render_group(source, root / "pages", GroupProfile("DEMO"))
            report = json.loads((root / "pages/view-report.json").read_text())
        self.assertEqual(counts["archive_publications"], 1)
        group = report["diagnostic_groups"][0]
        self.assertEqual(group["code"], "missing_analysis")
        self.assertEqual(
            group["entries"][0]["placement"], "Included in publication archive"
        )
        self.assertIn("fallback", group["entries"][0]["effect"])

    def test_unresolved_note_has_both_state_and_identifier_causes(self):
        note = publication(1, resource="pubnotes", status="Phase 1 Finished")
        del note["finalReferenceCode"]
        note["gal_publicationProvenance"] = {
            "source": "unresolved",
            "reason": "No unambiguous public identifier",
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps(snapshot(analysis(1), pubnotes=(note,))))
            with self.assertLogs("analysis_lister.views.build", level="WARNING"):
                counts = render_group(source, root / "pages", GroupProfile("DEMO"))
            report = json.loads((root / "pages/view-report.json").read_text())
        self.assertEqual(counts["records_with_diagnostics"], 1)
        self.assertEqual(counts["warning_issues"], 2)
        self.assertEqual(counts["archive_publications"], 0)
        self.assertEqual(
            {group["code"] for group in report["diagnostic_groups"]},
            {"unknown_state", "missing_public_identifier"},
        )
        self.assertTrue(
            all(
                group["entries"][0]["placement"] == "Excluded from publication archive"
                for group in report["diagnostic_groups"]
            )
        )

    def test_conflicting_and_unknown_relationship_reasons_remain_warnings(self):
        for reason, code in (
            ("publication points to a different analysis", "conflicting_analysis"),
            ("future relationship problem", "other_relationship"),
        ):
            trace = {
                "resource": "analyses",
                "reference": "ANA-DEMO-2099-01",
                "state": {"value": "phase0"},
                "inclusion": {"value": True},
                "relationship_issues": [{"reason": reason}],
            }
            entry = diagnostic_entry(trace)
            self.assertEqual(entry["issues"][0]["code"], code)
            self.assertEqual(entry["issues"][0]["level"], "warning")
            self.assertEqual(entry["placement"], "Included in ongoing analyses")
