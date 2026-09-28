"""Registry construction is independent of file loading and lookup validation."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.field_maps import REQUIRED_COLUMNS_ANALYSIS
from analysis_lister.glance.glance_registry import GlanceRegistry


class RegistryConstructionTests(unittest.TestCase):
    def test_constructor_copies_mapping_without_loading_or_reporting(self):
        row = dict.fromkeys(REQUIRED_COLUMNS_ANALYSIS, "")
        row.update(
            {"Reference Code": "ANA-TOPQ-2099-01", "Status": " Phase 0 is  Active "}
        )
        entry = Analysis.from_csv_dict(row)
        entries = {entry.ref_code: entry}
        with (
            patch("builtins.open", side_effect=AssertionError("unexpected file read")),
            patch(
                "analysis_lister.glance.glance_registry.validate_lookups",
                side_effect=AssertionError("unexpected lookup validation"),
            ),
            self.assertNoLogs(level="DEBUG"),
        ):
            registry = GlanceRegistry(
                entries, threshold_year="2022", last_modified_time="test"
            )
            empty = GlanceRegistry()
        entries.clear()
        self.assertIs(registry.get(entry.ref_code), entry)
        self.assertEqual(registry.analyses, [entry])
        self.assertEqual(registry.threshold_year, "2022")
        self.assertEqual(registry.last_modified_time, "test")
        self.assertEqual(empty.entries, {})
        self.assertEqual(empty.threshold_year, "2020")
        self.assertEqual(empty.last_modified_time, "")

    def test_json_factory_initializes_subclass_through_normal_constructor(self):
        class Registry(GlanceRegistry):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.initialized = True

        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.json"
            GlanceRegistry(threshold_year="2022", last_modified_time="test").store_json(
                snapshot
            )
            registry = Registry.from_json(snapshot)
        self.assertTrue(registry.initialized)
        self.assertEqual(registry.entries, {})
        self.assertEqual(registry.threshold_year, "2022")
        self.assertEqual(registry.last_modified_time, "test")


if __name__ == "__main__":
    unittest.main()
