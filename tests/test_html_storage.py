# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Failure-injection tests for CSV batches and registry snapshot writes."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.downloaders import csv_batch as html_download, html as downloader
from analysis_lister.downloaders.scope import SCOPE_FILENAME, load_scope
from analysis_lister.storage import (
    CSV_REFRESH_MARKER,
    atomic_write_text,
    require_complete_csv_batch,
)

HTML = "<span>Showing 1 to 1 of 1 results</span><table><tr><th>Reference Code</th></tr><tr><td>new</td></tr></table>"


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
                downloader.DownloadTable(
                    name=name,
                    url=f"https://example.test/{name}",
                    columns=("Reference Code",),
                    sort_by="reference_code",
                )
            )
        (self.csv_dir / SCOPE_FILENAME).write_text(json.dumps(load_scope().metadata()))
        (self.debug_dir / SCOPE_FILENAME).write_text(
            json.dumps(load_scope().metadata())
        )
        self.original = {p.name: p.read_bytes() for p in self.csv_dir.iterdir()}

    def assert_original(self):
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.csv_dir.iterdir()}, self.original
        )

    def test_local_batch_replaces_all_files_and_preserves_unrelated_files(self):
        keep = self.csv_dir / ".gitkeep"
        keep.touch()
        html_download.download_html_csvs(
            self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
        )
        for task in self.tasks:
            self.assertEqual(
                (self.csv_dir / task.csv_filename).read_text(),
                '"Reference Code"\n"new"\n',
            )
        self.assertTrue(keep.exists())
        self.assertEqual(len(list(self.csv_dir.iterdir())), 6)

    def test_table_definitions_can_be_reused_with_different_destinations(self):
        for name in ("first", "second"):
            destination = self.root / name
            html_download.download_html_csvs(
                self.tasks, destination, self.debug_dir, use_local_html=True
            )
            for task in self.tasks:
                self.assertEqual(
                    (destination / task.csv_filename).read_text(),
                    '"Reference Code"\n"new"\n',
                )
        self.assert_original()

    def test_table_metadata_controls_live_requests(self):
        table = downloader.DownloadTable(
            "notes", "https://example.test/notes", ("Reference Code",), "final_ref_code"
        )
        with patch.object(
            downloader.http.DataFetcher, "fetch_html", return_value=HTML
        ) as fetch:
            html_download.download_html_csvs(
                (table,), self.csv_dir, self.debug_dir, cookies={"session": "synthetic"}
            )
        fetch.assert_called_once_with(
            table.url,
            downloader.http.COMMON_PARAMS
            | load_scope().query_params()
            | {"s[0][name]": "final_ref_code"},
            {"session": "synthetic"},
        )
        self.assertEqual(
            (self.csv_dir / "notes.csv").read_text(), '"Reference Code"\n"new"\n'
        )

    def test_debug_tables_use_the_supplied_directory(self):
        debug_dir = self.root / "diagnostics" / "tables"
        with patch.object(downloader.http.DataFetcher, "fetch_html", return_value=HTML):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, debug_dir, cookies={}, debug=True
            )
        for task in self.tasks:
            self.assertEqual((debug_dir / task.html_filename).read_text(), HTML + "\n")

    def test_bad_final_table_preserves_entire_old_batch(self):
        for html in (
            "<html>login page</html>",
            "<table></table>",
            "<table><tr><th>Reference Code</th></tr></table>",
            "<table><tr><th>Renamed</th></tr><tr><td>new</td></tr></table>",
        ):
            with self.subTest(html=html):
                (self.debug_dir / "confnotes.html").write_text(html)
                with (
                    self.assertLogs(level="INFO") as logs,
                    self.assertRaises(ValueError),
                ):
                    html_download.download_html_csvs(
                        self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
                    )
                if "Renamed" in html:
                    self.assertTrue(
                        any("Columns missing" in line for line in logs.output),
                        logs.output,
                    )
                self.assert_original()

    def test_missing_final_html_preserves_old_batch(self):
        (self.debug_dir / "confnotes.html").unlink()
        with self.assertRaises(FileNotFoundError):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
            )
        self.assert_original()

    def test_failed_final_download_preserves_old_batch(self):
        with (
            patch.object(
                downloader.http.DataFetcher,
                "fetch_html",
                side_effect=[HTML, HTML, HTML, requests.ReadTimeout("timed out")],
            ),
            self.assertRaises(requests.ReadTimeout),
        ):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, self.debug_dir, cookies={}
            )
        self.assert_original()

    def test_promotion_failure_rolls_back_prior_replacements(self):
        replace = Path.replace

        def fail_third(source, target):
            if source.name == "pubnotes.csv" and source.parent.name != "previous":
                raise OSError("disk failure during promotion")
            return replace(source, target)

        with patch.object(Path, "replace", fail_third), self.assertRaises(OSError):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
            )
        self.assert_original()

    def test_first_download_failure_leaves_no_partial_csvs(self):
        for path in self.csv_dir.iterdir():
            path.unlink()
        replace = Path.replace

        def fail_second(source, target):
            if source.name == "papers.csv":
                raise OSError("disk failure")
            return replace(source, target)

        with patch.object(Path, "replace", fail_second), self.assertRaises(OSError):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
            )
        self.assertEqual(list(self.csv_dir.iterdir()), [])

    def test_interrupted_batch_is_rejected_and_successful_refresh_repairs_it(self):
        marker = self.csv_dir / CSV_REFRESH_MARKER
        marker.touch()
        with self.assertRaisesRegex(ValueError, "Incomplete CSV refresh"):
            require_complete_csv_batch(self.csv_dir)
        html_download.download_html_csvs(
            self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
        )
        self.assertFalse(marker.exists())

    def test_failed_rollback_keeps_marker_and_backups(self):
        replace = Path.replace

        def fail_promotion_and_rollback(source, target):
            if source.name == "papers.csv" or source.parent.name == "previous":
                raise OSError("filesystem unavailable")
            return replace(source, target)

        with (
            patch.object(Path, "replace", fail_promotion_and_rollback),
            self.assertLogs(
                "analysis_lister.downloaders.html", level="WARNING"
            ) as logs,
            self.assertRaises(OSError),
        ):
            html_download.download_html_csvs(
                self.tasks, self.csv_dir, self.debug_dir, use_local_html=True
            )
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Incomplete refresh; retaining staging files", logs.output[0])
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
        self.candidate = '{"synthetic": true}\n'

    def test_complete_snapshot_is_published(self):
        self.path.chmod(0o640)
        atomic_write_text(self.path, self.candidate)
        self.assertEqual(
            json.loads(self.path.read_text()),
            {"synthetic": True},
        )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_first_snapshot_creates_nested_parent_directories(self):
        destination = self.path.parent / "new" / "json" / "registry.json"
        atomic_write_text(destination, self.candidate)
        self.assertEqual(json.loads(destination.read_text()), {"synthetic": True})
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_failed_flush_or_replace_preserves_previous_snapshot(self):
        for target in ("analysis_lister.storage.os.fsync", "pathlib.Path.replace"):
            with (
                self.subTest(target=target),
                patch(target, side_effect=OSError("disk failure")),
            ):
                with self.assertRaises(OSError):
                    atomic_write_text(self.path, self.candidate)
                self.assertEqual(self.path.read_text(), self.old)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == "__main__":
    unittest.main()
