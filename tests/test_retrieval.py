# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Unfiltered downloads and complete-batch provenance, using synthetic HTML."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from grove import cli
from grove.downloaders import auth, csv_batch, html
from grove.downloaders.manifest import (
    HTML_MANIFEST,
    make_manifest,
    read_manifest,
    validate_manifest,
)

HTML = "<span>Showing 1 to 1 of 1 results</span><table><tr><th>Reference Code</th></tr><tr><td>DEMO-2099-01</td></tr></table>"


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tasks = tuple(
            html.DownloadTable(
                name,
                f"https://example.test/{name}",
                "reference_code",
            )
            for name in ("analyses", "papers", "pubnotes")
        )

    def test_download_commands_reject_config_before_authentication(self):
        for command in ("download-api", "download-html"):
            with (
                self.subTest(command=command),
                patch.object(auth, "resolve_cookies") as credentials,
                patch("sys.stderr", io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main([command, "--config", "unused.toml"])
            self.assertEqual(error.exception.code, 2)
            credentials.assert_not_called()

    def test_all_requests_are_unfiltered_and_saved_html_can_be_replayed(self):
        destination, saved = self.root / "csv", self.root / "html"
        with patch.object(
            html.http.DataFetcher, "fetch_html", return_value=HTML
        ) as network:
            csv_batch.download_html_csvs(self.tasks, destination, saved, debug=True)
        self.assertEqual(network.call_count, len(self.tasks))
        for task, call in zip(self.tasks, network.call_args_list, strict=True):
            self.assertEqual(
                call.args[1], html.http.COMMON_PARAMS | {"s[0][name]": task.sort_by}
            )
        manifest = read_manifest(destination, self.tasks)
        self.assertEqual(manifest["selection"], "all-accessible")
        self.assertEqual(read_manifest(saved, self.tasks), manifest)
        with patch.object(
            html.http.DataFetcher, "fetch_html", side_effect=AssertionError("network")
        ):
            replay = self.root / "replay"
            csv_batch.download_html_csvs(self.tasks, replay, saved, use_local_html=True)
        self.assertEqual(read_manifest(replay, self.tasks), manifest)

    def test_cli_saved_html_replay_preserves_csv_bytes(self):
        tasks = html.download_tasks()
        for index, separator in enumerate(("\n", "\r\n", "\r", "\r\n\n\r")):
            with self.subTest(separator=repr(separator)):
                root = self.root / str(index)
                destination, saved, replay = (
                    root / "csv",
                    root / "html",
                    root / "replay",
                )
                responses = {
                    task.url: (
                        "<span>Showing 1 to 1 of 1 results</span><table><tr>"
                        f"<th>{task.key}</th><th>Title</th></tr><tr>"
                        f"<td>{task.prefix}DEMO-2099-01</td>"
                        f"<td> Invented café{separator}title </td></tr></table>"
                    )
                    for task in tasks
                }
                with (
                    patch.object(auth, "resolve_cookies", return_value={}),
                    patch.object(
                        html.http.DataFetcher,
                        "fetch_html",
                        side_effect=lambda url, *_, responses=responses: responses[url],
                    ),
                    patch("sys.stdout", io.StringIO()),
                ):
                    cli.main(
                        [
                            "download-html",
                            "--csv-dir",
                            str(destination),
                            "--save-html",
                            str(saved),
                        ]
                    )
                before = {path.name: path.read_bytes() for path in saved.iterdir()}
                for task in tasks:
                    self.assertEqual(
                        before[task.html_filename],
                        (responses[task.url] + "\n").encode("utf-8"),
                    )
                with (
                    patch.object(
                        auth, "resolve_cookies", side_effect=AssertionError("login")
                    ),
                    patch.object(
                        html.http.DataFetcher,
                        "fetch_html",
                        side_effect=AssertionError("network"),
                    ),
                    patch("sys.stdout", io.StringIO()),
                ):
                    cli.main(
                        [
                            "download-html",
                            "--from-html",
                            str(saved),
                            "--csv-dir",
                            str(replay),
                        ]
                    )
                for task in tasks:
                    self.assertEqual(
                        (destination / task.csv_filename).read_bytes(),
                        (replay / task.csv_filename).read_bytes(),
                    )
                self.assertEqual(
                    {path.name: path.read_bytes() for path in saved.iterdir()}, before
                )

    def test_replay_warns_on_legacy_manifest_and_writes_current_metadata(self):
        from grove.provenance import generator_metadata

        saved = self.root / "saved"
        saved.mkdir()
        for task in self.tasks:
            (saved / task.html_filename).write_text(HTML)
        manifest = make_manifest(self.tasks)
        manifest.pop("generator")
        manifest["schema_version"] = 1
        source = saved / HTML_MANIFEST
        source.write_text(json.dumps(manifest))
        before = source.read_bytes()
        with (
            self.assertLogs("grove.provenance", level="WARNING"),
            patch.object(
                html.http.DataFetcher,
                "fetch_html",
                side_effect=AssertionError("network"),
            ),
        ):
            csv_batch.download_html_csvs(
                self.tasks, self.root / "csv", saved, use_local_html=True
            )
        result = read_manifest(self.root / "csv", self.tasks)
        self.assertNotIn("schema_version", result)
        self.assertEqual(result["generator"], generator_metadata())
        self.assertEqual(result["fetched_at"], manifest["fetched_at"])
        self.assertEqual(source.read_bytes(), before)

    def test_filtered_or_malformed_manifests_are_rejected(self):
        for change in (
            {"selection": "filtered"},
            {"selection": {}},
            {"tables": {}},
            {"schema": "unknown"},
        ):
            manifest = make_manifest(self.tasks) | change
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, "all-accessible"),
            ):
                validate_manifest(manifest, self.tasks)

    def test_filtered_destination_is_rejected_before_network_or_overwrite(self):
        destination = self.root / "csv"
        destination.mkdir()
        path = destination / HTML_MANIFEST
        path.write_text(
            json.dumps(make_manifest(self.tasks) | {"selection": "filtered"})
        )
        original = path.read_bytes()
        with (
            patch.object(html.http.DataFetcher, "fetch_html") as network,
            self.assertRaisesRegex(ValueError, "all-accessible"),
        ):
            csv_batch.download_html_csvs(self.tasks, destination, self.root / "html")
        network.assert_not_called()
        self.assertEqual(path.read_bytes(), original)

    def test_saved_html_requires_complete_unfiltered_metadata(self):
        saved = self.root / "saved"
        saved.mkdir()
        for task in self.tasks:
            (saved / task.html_filename).write_text(HTML)
        with self.assertRaises(FileNotFoundError):
            csv_batch.download_html_csvs(
                self.tasks, self.root / "csv", saved, use_local_html=True
            )
        (saved / HTML_MANIFEST).write_text(
            json.dumps(make_manifest(self.tasks) | {"tables": {}})
        )
        with self.assertRaisesRegex(ValueError, "all-accessible"):
            csv_batch.download_html_csvs(
                self.tasks, self.root / "csv", saved, use_local_html=True
            )
        self.assertFalse((self.root / "csv").exists())
