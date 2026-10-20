# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Missing relationship references are normal for scoped and historical data."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from analysis_lister.lookup_dicts.clones import Clones
from analysis_lister.lookup_review import lookup_review_notices


class LookupReviewTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(
            patch.dict(Clones, {"DEMO-2099-02": "DEMO-2099-01"}, clear=True)
        )

    def test_present_relationship_needs_no_review(self):
        registry = SimpleNamespace(
            entries={"DEMO-2099-01": object(), "DEMO-2099-02": object()}
        )
        self.assertEqual(lookup_review_notices(registry), [])

    def test_entirely_absent_relationship_is_silent_and_retained(self):
        registry = SimpleNamespace(entries={})
        self.assertEqual(lookup_review_notices(registry), [])
        self.assertEqual(Clones, {"DEMO-2099-02": "DEMO-2099-01"})

    def test_partial_relationship_is_informational_and_retained(self):
        for present, missing in (
            ("DEMO-2099-01", "DEMO-2099-02"),
            ("DEMO-2099-02", "DEMO-2099-01"),
        ):
            with self.subTest(present=present):
                notices = lookup_review_notices(
                    SimpleNamespace(entries={present: object()})
                )
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0][0], logging.INFO)
                self.assertIn(missing, notices[0][1])
                self.assertIn("this snapshot", notices[0][1])
                self.assertEqual(Clones, {"DEMO-2099-02": "DEMO-2099-01"})

    def test_counterpart_outside_view_is_not_missing_from_full_snapshot(self):
        registry = SimpleNamespace(
            entries={"DEMO-2099-01": object(), "DEMO-2099-02": object()}
        )
        self.assertEqual(
            lookup_review_notices(registry, relevant_refs={"DEMO-2099-01"}), []
        )

    def test_missing_counterpart_unrelated_to_view_is_silent(self):
        registry = SimpleNamespace(entries={"DEMO-2099-01": object()})
        self.assertEqual(
            lookup_review_notices(registry, relevant_refs={"OTHER-2099-01"}), []
        )

    def test_missing_counterpart_relevant_to_view_is_reported(self):
        registry = SimpleNamespace(entries={"DEMO-2099-01": object()})
        notices = lookup_review_notices(registry, relevant_refs={"DEMO-2099-01"})
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][0], logging.INFO)
        self.assertIn("DEMO-2099-02", notices[0][1])
