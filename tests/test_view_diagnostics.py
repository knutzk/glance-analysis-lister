# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for DiagnosticReportTests."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from view_fixtures import analysis, snapshot

from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.report import diagnostic_entry


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
            "Needs review (also counted in diagnostics; excluded from ongoing)",
            messages,
        )
        self.assertIn(uncertain["referenceCode"], messages)
        self.assertIn(
            "source does not establish an ongoing or completed state", messages
        )
        self.assertIn("Diagnostics: analyses/" + linked["referenceCode"], messages)
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
