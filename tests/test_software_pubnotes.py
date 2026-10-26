# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for SoftwarePubNoteTests."""

import unittest

from view_fixtures import analysis, publication, snapshot

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import pubnotes_page
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile


class SoftwarePubNoteTests(unittest.TestCase):
    def test_released_software_note_completes_its_linked_analysis(self):
        record = analysis(1, status="Phase 0 Finished")
        note = publication(
            1,
            resource="pubnotes",
            related=record["referenceCode"],
            status="Phase 1 Finished",
        )
        note["finalReferenceCode"] = None
        note["gal_finalReferenceCode"] = "ATL-SOFT-PUB-2099-001"
        record["relatedPublications"] = [
            {"type": "PUB note", "referenceCode": note["temporaryReferenceCode"]}
        ]
        view = prepare_group(
            CuratedRegistry(snapshot(record, pubnotes=(note,))), GroupProfile("DEMO")
        )
        trace = next(row for row in view.decisions if row["resource"] == "analyses")
        self.assertEqual(trace["state"]["value"], "completed")
        self.assertEqual(view.needs_review, ())
        self.assertEqual(view.ongoing, ())
        self.assertEqual(view.archive[0].state, "released")
        self.assertIn("ATL-SOFT-PUB-2099-001", pubnotes_page(view))
