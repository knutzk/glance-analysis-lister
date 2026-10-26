# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for AwaitingPublicationReviewTests."""

import json
import unittest

from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.analysis_states import analysis_state
from analysis_lister.views.markdown.pages import ongoing_page
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile
from analysis_lister.views.publication_states import publication_state
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
            row.metadata["stage_order"],
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

    def test_finished_paper_review_phases_remain_ongoing_until_submission(self):
        for status in ("Phase 1 Finished", "Phase 2 Finished"):
            with self.subTest(status=status):
                record = analysis(1, status="Phase 0 Finished")
                paper = publication(
                    1, related=record["referenceCode"], status=status, date=None
                )
                paper["publicationPhase"]["gal_dois"] = []
                paper["phase1"] = {"draftReleasedDate": "2099-01-02"}
                paper["phase2"] = (
                    {"draft2ReleasedDate": "2099-02-03"}
                    if status == "Phase 2 Finished"
                    else {}
                )
                record["relatedPublications"] = [
                    {"type": "Paper", "referenceCode": paper["referenceCode"]}
                ]
                data = snapshot(record, papers=(paper,))
                view = prepare_group(CuratedRegistry(data), GroupProfile("DEMO"))
                self.assertEqual(view.needs_review, ())
                self.assertEqual(len(view.ongoing), 1)
                self.assertEqual(view.ongoing[0].stage, "publication_review")
                self.assertEqual(view.archive, ())
                self.assertTrue(view.ongoing[0].progress[-2]["reached"])
                self.assertEqual(
                    view.ongoing[0].progress[-1]["reached"],
                    status == "Phase 2 Finished",
                )
                report = build_report(view, "synthetic.json", json.dumps(data).encode())
                self.assertEqual(report["records_with_diagnostics"], [])
                trace = next(t for t in view.decisions if t["resource"] == "papers")
                self.assertEqual(trace["state"]["inputs"]["status"], status)

                paper["publicationPhase"]["arXivSubmissionDate"] = "2099-03-04"
                view = prepare_group(
                    CuratedRegistry(snapshot(record, papers=(paper,))),
                    GroupProfile("DEMO"),
                )
                self.assertEqual(view.ongoing, ())
                self.assertEqual(view.archive[0].state, "submitted")
                paper["publicationPhase"]["publishedOnlineDate"] = "2099-04-05"
                self.assertEqual(publication_state(paper, "papers").value, "published")

    def test_unrecognised_paper_state_is_not_inferred_from_finished_text(self):
        paper = publication(1, status="Unrecognised Phase Finished", date=None)
        self.assertEqual(publication_state(paper, "papers").value, "unknown")
        note = publication(
            1, resource="confnotes", status="Phase 2 Finished", date=None
        )
        self.assertEqual(publication_state(note, "confnotes").value, "unknown")
