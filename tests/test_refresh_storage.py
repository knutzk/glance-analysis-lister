"""Failure-injection tests for CSV batches and registry snapshot writes."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_csv_files as downloader
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.storage import CSV_REFRESH_MARKER

HTML = "<table><tr><th>Reference Code</th></tr><tr><td>new</td></tr></table>"


class CsvBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.csv_dir = self.root / "csv"
        self.csv_dir.mkdir()
        self.debug_dir = self.root / "debug"
        self.debug_dir.mkdir()
        self.tasks = []
        for name in ("analyses", "papers", "pubnotes", "confnotes"):
            output = self.csv_dir / f"{name}.csv"
            output.write_text(f"old {name}\n")
            (self.debug_dir / f"{name}.html").write_text(HTML)
            self.tasks.append(
                {
                    "output_csv": output,
                    "debug_file": f"{name}.html",
                    "column_filter": ["Reference Code"],
                    "url": f"https://example.test/{name}",
                    "custom_params": {},
                }
            )
        self.original = {p.name: p.read_bytes() for p in self.csv_dir.iterdir()}
        for name, value in (("CSV_DIR", self.csv_dir), ("DEBUG_DIR", self.debug_dir)):
            patcher = patch.object(downloader, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def assert_original(self):
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.csv_dir.iterdir()}, self.original
        )

    def test_local_batch_replaces_all_files_and_preserves_unrelated_files(self):
        keep = self.csv_dir / ".gitkeep"
        keep.touch()
        downloader.refresh_csv_files(self.tasks, use_local_html=True)
        for task in self.tasks:
            self.assertEqual(
                task["output_csv"].read_text(), '"Reference Code"\n"new"\n'
            )
        self.assertTrue(keep.exists())
        self.assertEqual(len(list(self.csv_dir.iterdir())), 5)

    def test_bad_final_table_preserves_entire_old_batch(self):
        for html in (
            "<html>login page</html>",
            "<table></table>",
            "<table><tr><th>Reference Code</th></tr></table>",
            "<table><tr><th>Renamed</th></tr><tr><td>new</td></tr></table>",
        ):
            with self.subTest(html=html):
                (self.debug_dir / "confnotes.html").write_text(html)
                with self.assertRaises(ValueError):
                    downloader.refresh_csv_files(self.tasks, use_local_html=True)
                self.assert_original()

    def test_missing_final_html_preserves_old_batch(self):
        (self.debug_dir / "confnotes.html").unlink()
        with self.assertRaises(FileNotFoundError):
            downloader.refresh_csv_files(self.tasks, use_local_html=True)
        self.assert_original()

    def test_failed_final_download_preserves_old_batch(self):
        with (
            patch.object(
                downloader.DataFetcher,
                "fetch_html",
                side_effect=[HTML, HTML, HTML, requests.ReadTimeout("timed out")],
            ),
            self.assertRaises(requests.ReadTimeout),
        ):
            downloader.refresh_csv_files(self.tasks, cookies={})
        self.assert_original()

    def test_promotion_failure_rolls_back_prior_replacements(self):
        replace = Path.replace

        def fail_third(source, target):
            if source.name == "pubnotes.csv" and source.parent.name != "previous":
                raise OSError("disk failure during promotion")
            return replace(source, target)

        with patch.object(Path, "replace", fail_third), self.assertRaises(OSError):
            downloader.refresh_csv_files(self.tasks, use_local_html=True)
        self.assert_original()

    def test_first_download_failure_leaves_no_partial_csvs(self):
        for task in self.tasks:
            task["output_csv"].unlink()
        replace = Path.replace

        def fail_second(source, target):
            if source.name == "papers.csv":
                raise OSError("disk failure")
            return replace(source, target)

        with patch.object(Path, "replace", fail_second), self.assertRaises(OSError):
            downloader.refresh_csv_files(self.tasks, use_local_html=True)
        self.assertEqual(list(self.csv_dir.iterdir()), [])

    def test_interrupted_batch_is_rejected_and_successful_refresh_repairs_it(self):
        marker = self.csv_dir / CSV_REFRESH_MARKER
        marker.touch()
        with self.assertRaisesRegex(ValueError, "Incomplete CSV refresh"):
            GlanceRegistry(csv_dir=self.csv_dir)
        downloader.refresh_csv_files(self.tasks, use_local_html=True)
        self.assertFalse(marker.exists())

    def test_failed_rollback_keeps_marker_and_backups(self):
        replace = Path.replace

        def fail_promotion_and_rollback(source, target):
            if source.name == "papers.csv" or source.parent.name == "previous":
                raise OSError("filesystem unavailable")
            return replace(source, target)

        with (
            patch.object(Path, "replace", fail_promotion_and_rollback),
            self.assertRaises(OSError),
        ):
            downloader.refresh_csv_files(self.tasks, use_local_html=True)
        self.assertTrue((self.csv_dir / CSV_REFRESH_MARKER).exists())
        backups = list(self.csv_dir.glob(".refresh-*/previous/analyses.csv"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original["analyses.csv"])


class RegistryWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "registry.json"
        self.old = '{"previous": true}\n'
        self.path.write_text(self.old)
        self.registry = GlanceRegistry.__new__(GlanceRegistry)
        self.registry._analyses = {}
        self.registry.threshold_year = "2020"
        self.registry.last_modified_time = "test"

    def test_complete_snapshot_is_published(self):
        self.path.chmod(0o640)
        self.registry.store_json(self.path)
        self.assertEqual(
            json.loads(self.path.read_text()),
            {"entries": {}, "threshold_year": "2020", "last_modified_time": "test"},
        )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_failed_flush_or_replace_preserves_previous_snapshot(self):
        for target in ("analysis_lister.storage.os.fsync", "pathlib.Path.replace"):
            with (
                self.subTest(target=target),
                patch(target, side_effect=OSError("disk failure")),
            ):
                with self.assertRaises(OSError):
                    self.registry.store_json(self.path)
                self.assertEqual(self.path.read_text(), self.old)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
