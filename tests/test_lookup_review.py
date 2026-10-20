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

    def test_absent_references_are_informational_and_retained(self):
        registry = SimpleNamespace(entries={})
        notices = lookup_review_notices(registry)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][0], logging.INFO)
        self.assertIn("DEMO-2099-01", notices[0][1])
        self.assertIn("Retain historical mappings", notices[0][1])
        self.assertEqual(Clones, {"DEMO-2099-02": "DEMO-2099-01"})
