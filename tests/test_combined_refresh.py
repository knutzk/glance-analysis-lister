# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise the combined workflow against synthetic GLANCE tables, without a login."""

import html
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister import download as downloader, refresh
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.lookup_dicts.clones import Clones


class CombinedRefreshTests(unittest.TestCase):
    def setUp(self):
        # Synthetic registries have no relationship to maintained historical mappings.
        self.enterContext(patch.dict(Clones, {}, clear=True))
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.csv_dir = self.root / "csv"
        self.debug_dir = self.root / "debug"
        self.json_dir = self.root / "json"
        for directory in (self.csv_dir, self.debug_dir, self.json_dir):
            directory.mkdir()
        for task in downloader.download_tasks():
            columns = list(dict.fromkeys(task.columns))
            values = dict.fromkeys(columns, "")
            values["Reference Code"] = (
                "ANA-TOPQ-2025-01" if task.name == "analyses" else "TOPQ-2000-01"
            )
            if task.name in ("confnotes", "pubnotes"):
                prefix = "CONF" if task.name == "confnotes" else "PUB"
                values["Temporary Reference Code"] = f"{prefix}-TOPQ-2000-01"
            values["Status"] = " Phase 0 is  Active "
            values["Subgroups"] = "TOPQ - Cross-section"
            if task.name == "analyses":
                self.analysis_row = values
            table = (
                "<table><tr>"
                + "".join(f"<th>{html.escape(col)}</th>" for col in columns)
                + "</tr><tr>"
                + "".join(f"<td>{html.escape(values[col])}</td>" for col in columns)
                + "</tr></table>"
            )
            (self.debug_dir / task.html_filename).write_text(table)
            (self.csv_dir / task.csv_filename).write_text("previous CSV\n")
        self.snapshot = self.json_dir / "glance_registry.json"
        self.write_baseline(1)

    def write_baseline(self, count):
        entries = {}
        for index in range(count):
            row = self.analysis_row | {
                "Reference Code": f"ANA-TOPQ-2025-{index + 1:02}"
            }
            entry = Analysis.from_csv_dict(row)
            entries[entry.ref_code] = entry
        registry = GlanceRegistry(entries, last_modified_time="previous")
        registry.store_json(self.snapshot)
        self.previous_json = self.snapshot.read_bytes()

    def run_refresh(self, *, force=False):
        with (
            patch.object(
                downloader.CookieManager,
                "load_cookies",
                side_effect=AssertionError("offline mode must not read credentials"),
            ),
            patch.object(
                downloader.DataFetcher,
                "fetch_html",
                side_effect=AssertionError("offline mode must not fetch"),
            ),
        ):
            refresh.refresh_analysis_lists(
                self.csv_dir,
                self.debug_dir,
                self.snapshot,
                force=force,
                use_local_html=True,
            )

    def assert_unchanged(self):
        self.assertEqual(self.snapshot.read_bytes(), self.previous_json)
        self.assertEqual(len(list(self.csv_dir.iterdir())), 4)
        for path in self.csv_dir.iterdir():
            self.assertEqual(path.read_text(), "previous CSV\n")

    def test_success_publishes_matching_csvs_and_snapshot(self):
        with self.assertNoLogs(level="WARNING"):
            self.run_refresh()
            from_csv = GlanceRegistry.from_csv(csv_dir=self.csv_dir)
            from_json = GlanceRegistry.from_json(self.snapshot)
        self.assertEqual(from_csv.entries, from_json.entries)
        self.assertEqual(from_csv.retrieval_scope, from_json.retrieval_scope)
        self.assertIsNotNone(from_json.retrieval_scope)
        self.assertEqual(from_csv.last_modified_time, from_json.last_modified_time)
        self.assertEqual(len(from_json.entries), 1)
        self.assertEqual(len(list(self.csv_dir.iterdir())), 5)

    def test_csv_factory_initializes_subclass_through_normal_constructor(self):
        class Registry(GlanceRegistry):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.initialized = True

        self.run_refresh()
        registry = Registry.from_csv(self.csv_dir)
        self.assertTrue(registry.initialized)
        self.assertEqual(
            registry.entries, GlanceRegistry.from_json(self.snapshot).entries
        )

    def test_count_drop_preserves_both_inputs_and_force_allows_it(self):
        self.write_baseline(2)
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.run_refresh()
        self.assert_unchanged()
        with self.assertLogs("analysis_lister.refresh", level="WARNING") as logs:
            self.run_refresh(force=True)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Writing the registry despite", logs.output[0])
        self.assertEqual(len(GlanceRegistry.from_json(self.snapshot).entries), 1)

    def test_bad_html_aborts_even_with_force(self):
        (self.debug_dir / "confnotes.html").write_text("<html>login required</html>")
        with self.assertRaises(ValueError):
            self.run_refresh(force=True)
        self.assert_unchanged()

    def test_registry_construction_failure_preserves_both(self):
        with (
            patch.object(
                refresh, "build_registry", side_effect=ValueError("bad record")
            ),
            self.assertRaises(ValueError),
        ):
            self.run_refresh()
        self.assert_unchanged()

    def test_staged_serialization_failure_preserves_both(self):
        with (
            patch.object(
                GlanceRegistry, "store_json", side_effect=OSError("disk full")
            ),
            self.assertRaises(OSError),
        ):
            self.run_refresh()
        self.assert_unchanged()

    def test_final_snapshot_failure_rolls_back_csvs(self):
        with (
            patch.object(
                refresh, "atomic_write_text", side_effect=OSError("disk full")
            ),
            self.assertRaises(OSError),
        ):
            self.run_refresh()
        self.assert_unchanged()

    def test_csv_promotion_failure_preserves_snapshot_and_rolls_back(self):
        replace = Path.replace

        def fail_second_csv(source, target):
            if source.name == "papers.csv" and source.parent.name != "previous":
                raise OSError("cannot replace CSV")
            return replace(source, target)

        with patch.object(Path, "replace", fail_second_csv), self.assertRaises(OSError):
            self.run_refresh()
        self.assert_unchanged()

    def test_first_refresh_needs_no_previous_snapshot(self):
        self.snapshot.unlink()
        self.run_refresh()
        self.assertEqual(len(GlanceRegistry.from_json(self.snapshot).entries), 1)

    def test_first_refresh_creates_csv_and_nested_snapshot_directories(self):
        self.snapshot.unlink()
        self.json_dir.rmdir()
        for path in self.csv_dir.iterdir():
            path.unlink()
        self.csv_dir.rmdir()
        self.snapshot = self.json_dir / "nested" / "glance_registry.json"
        self.run_refresh()
        from_csv = GlanceRegistry.from_csv(csv_dir=self.csv_dir)
        from_json = GlanceRegistry.from_json(self.snapshot)
        self.assertEqual(from_csv.entries, from_json.entries)
        self.assertEqual(len(from_json.entries), 1)
        self.assertEqual(len(list(self.csv_dir.iterdir())), 5)
        self.assertEqual(list(self.snapshot.parent.iterdir()), [self.snapshot])

    def test_unusable_snapshot_parent_rolls_back_csvs(self):
        previous_snapshot = self.snapshot
        blocker = self.root / "not-a-directory"
        blocker.write_text("Keep this file")
        self.snapshot = blocker / "nested" / "glance_registry.json"
        with self.assertRaises(OSError):
            self.run_refresh()
        self.snapshot = previous_snapshot
        self.assert_unchanged()
        self.assertEqual(blocker.read_text(), "Keep this file")


if __name__ == "__main__":
    unittest.main()
