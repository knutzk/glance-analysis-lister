# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for ClosedAnalysisLinkTests."""

import json
import unittest

from view_fixtures import analysis, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.report import build_report


class ClosedAnalysisLinkTests(unittest.TestCase):
    def test_missing_publication_link_is_not_diagnostic_for_closed_analysis(self):
        for status in ("Closed", "Phase 0 Active", "Phase 0 Finished"):
            with self.subTest(status=status):
                record = analysis(1, status=status)
                record["relatedPublications"] = [
                    {"type": "CONF note", "referenceCode": "CONF-DEMO-2099-99"}
                ]
                data = snapshot(record)
                view = prepare_group(CuratedRegistry(data), GroupProfile("DEMO"))
                report = build_report(view, "synthetic.json", json.dumps(data).encode())
                trace = next(t for t in view.decisions if t["resource"] == "analyses")
                self.assertEqual(
                    trace["state"]["inputs"]["linked_publication_states"][0]["state"],
                    "unknown",
                )
                if status == "Closed":
                    self.assertEqual(trace["state"]["value"], "closed")
                    self.assertEqual(trace["relationship_issues"], [])
                    self.assertEqual(report["records_with_diagnostics"], [])
                    self.assertEqual(report["counts"]["records_with_diagnostics"], 0)
                else:
                    self.assertEqual(
                        trace["relationship_issues"][0]["reason"],
                        "unresolved publication link",
                    )
                    self.assertEqual(report["counts"]["records_with_diagnostics"], 1)
