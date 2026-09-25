"""Snapshot-relative review distinguishes stale overrides from historical data."""

import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.enums import PublicationState
from analysis_lister.lookup_dicts.review import lookup_review_notices


class LookupReviewTests(unittest.TestCase):
    def registry(self, state=PublicationState.PUBLISHED):
        source = SimpleNamespace(
            ref_code="TOPQ-2025-01", pub_state=PublicationState.PAST_PHASE0
        )
        target = SimpleNamespace(ref_code="TOPQ-2025-02", pub_state=state)
        return SimpleNamespace(
            entries={source.ref_code: source, target.ref_code: target},
            unaccounted=[source],
            analyses=[],
            papers=[target] if state == PublicationState.PUBLISHED else [],
            confnotes=[],
            pubnotes=[],
        )

    def setUp(self):
        for name, value in (
            ("KnownDuplicates", {"TOPQ-2025-01": "TOPQ-2025-02"}),
            ("DoiOrder", {}),
        ):
            patcher = patch.dict(
                f"analysis_lister.lookup_dicts.review.{name}", value, clear=True
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_active_mapping_needs_no_review(self):
        self.assertEqual(lookup_review_notices(self.registry()), [])

    def test_closed_target_is_reported_without_changing_mapping(self):
        registry = self.registry(PublicationState.CLOSED)
        notices = lookup_review_notices(registry)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][0], logging.WARNING)
        self.assertIn("target TOPQ-2025-02 is CLOSED", notices[0][1])
        self.assertIn("known_duplicates.py", notices[0][1])
        self.assertEqual(len(registry.entries), 2)

    def test_absent_source_and_target_are_one_review_notice(self):
        registry = self.registry()
        registry.entries = {}
        notices = lookup_review_notices(registry)
        self.assertEqual(len(notices), 1)
        self.assertIn("duplicate is absent from this snapshot", notices[0][1])
        self.assertIn("target TOPQ-2025-02 is absent from this snapshot", notices[0][1])
        self.assertNotIn("no longer in GLANCE", notices[0][1])

    def test_resolved_duplicate_needs_review(self):
        registry = self.registry()
        registry.entries["TOPQ-2025-01"].pub_state = PublicationState.CLOSED
        registry.unaccounted = []
        self.assertIn("duplicate is now CLOSED", lookup_review_notices(registry)[0][1])

    def test_absent_doi_override_is_informational(self):
        with patch.dict(
            "analysis_lister.lookup_dicts.review.DoiOrder",
            {"TOPQ-1999-01": ["10.1007/example"]},
        ):
            notices = lookup_review_notices(self.registry())
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][0], logging.INFO)
        self.assertIn("may be historical", notices[0][1])

    def test_doi_override_on_nonpaper_is_reported(self):
        with patch.dict(
            "analysis_lister.lookup_dicts.review.DoiOrder",
            {"TOPQ-2025-01": ["10.1007/example"]},
        ):
            notices = lookup_review_notices(self.registry())
        self.assertEqual(notices[0][0], logging.WARNING)
        self.assertIn("its DOI override is unused", notices[0][1])


if __name__ == "__main__":
    unittest.main()
