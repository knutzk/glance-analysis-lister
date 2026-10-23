# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for AwaitingPublicationReviewTests."""

import json
import unittest

from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.analyses import analysis_state
from analysis_lister.views.markdown.pages import ongoing_page
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.report import build_report


class AwaitingPublicationReviewTests(unittest.TestCase):
    def test_created_note_after_skipped_phase0_remains_ongoing_without_diagnostics(
        self,
    ):
        record = analysis(1, status="Phase 0 Finished")
        record["phase0"]["state"] = "Skipped to PUB Note"
        note = publication(
            1,
            resource="pubnotes",
            related=record["referenceCode"],
            status="Created",
            date=None,
        )
        note["finalReferenceCode"] = None
        note["phase1"]["publicWebPageUrlForFiguresAndTables"] = None
        record["relatedPublications"] = [
            {"type": "PUB note", "referenceCode": note["temporaryReferenceCode"]}
        ]
        data = snapshot(record, pubnotes=(note,))
        view = prepare_group(CuratedRegistry(data), GroupProfile("DEMO"))
        self.assertEqual(view.needs_review, ())
        self.assertEqual(len(view.ongoing), 1)
        row = view.ongoing[0]
        self.assertEqual(row.stage, "awaiting_publication_review")
        self.assertIn("Awaiting publication review", ongoing_page(view))
        self.assertEqual(
            row.filter_metadata["stage_order"],
            sum(
                1 << index for index, step in enumerate(row.progress) if step["reached"]
            ),
        )
        trace = next(t for t in view.decisions if t["resource"] == "analyses")
        self.assertEqual(
            trace["state"]["inputs"]["phase0.state"], "Skipped to PUB Note"
        )
        report = build_report(view, "synthetic.json", json.dumps(data).encode())
        self.assertEqual(report["records_with_diagnostics"], [])
        self.assertEqual(report["counts"]["ongoing_analyses"], 1)

    def test_awaiting_review_requires_resolved_created_publication(self):
        record = analysis(1, status="Phase 0 Finished")
        cases = [
            ([], "unknown"),
            (["not_started"], "awaiting_publication_review"),
            (["released", "not_started"], "awaiting_publication_review"),
            (["unknown", "not_started"], "unknown"),
            (["released"], "completed"),
            (["under_review", "not_started"], "publication_review"),
        ]
        for states, expected in cases:
            with self.subTest(states=states):
                self.assertEqual(
                    analysis_state(
                        record, [{"state": state} for state in states]
                    ).value,
                    expected,
                )
        record["status"] = "Phase 0 Active"
        self.assertEqual(
            analysis_state(record, [{"state": "not_started"}]).value, "phase0"
        )
