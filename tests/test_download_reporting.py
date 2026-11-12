# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Consistent command summaries and evidence-based failure reporting, offline."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from test_api import client_for

from grove import cli
from grove.downloaders.api import collect_registry, publish_registry
from grove.downloaders.html import download_tasks
from grove.downloaders.manifest import (
    CSV_REFRESH_MARKER,
    HTML_MANIFEST,
    make_manifest,
)
from grove.downloaders.reporting import run_download


class DownloadReportingTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saved = self.root / "saved"
        self.saved.mkdir()
        tasks = download_tasks()
        (self.saved / HTML_MANIFEST).write_text(json.dumps(make_manifest(tasks)))
        for task in tasks:
            rows = "".join(
                f"<tr><td>{task.prefix}DEMO-2099-{number:02}</td><td>Invented content</td></tr>"
                for number in (1, 2)
            )
            (self.saved / task.html_filename).write_text(
                "<span>Showing 1 to 2 of 2 results</span><table><tr>"
                f"<th>{task.key}</th><th>Short Title</th></tr>{rows}</table>"
            )
        self.csv_dir = self.root / "csv"

    def html_command(self):
        return [
            "download-html",
            "--from-html",
            str(self.saved),
            "--csv-dir",
            str(self.csv_dir),
            "--color",
            "never",
        ]

    def seed_api(self, path, count=1):
        candidate = collect_registry(client_for(count))
        candidate["source"]["base_url"] = "https://example.test/api"
        publish_registry(candidate, path, allow_count_drop=True)

    def test_api_success_reports_counts_timing_validation_and_files(self):
        destination = self.root / "api.json"
        stdout = io.StringIO()
        with (
            patch("stare.Glance") as glance,
            patch("stare.auth.TokenManager"),
            patch("stare.settings.StareSettings") as settings,
            patch(
                "grove.downloaders.reporting.perf_counter",
                side_effect=[10, 12.5],
            ),
            redirect_stdout(stdout),
            redirect_stderr(io.StringIO()),
        ):
            settings.return_value.base_url = "https://example.test/api"
            glance.return_value.__enter__.return_value = client_for(2)
            cli.main(
                [
                    "download-api",
                    "--output",
                    str(destination),
                    "--allow-count-drop",
                    "--color",
                    "never",
                ]
            )
        text = stdout.getvalue()
        self.assertIn("API download complete", text)
        self.assertIn(str(destination), text)
        self.assertIn("2.50s (including authentication and publication)", text)
        self.assertIn("count-drop guard explicitly overridden", text)
        self.assertRegex(text, r"Total records\s+8")
        for resource in ("analyses", "papers", "confnotes", "pubnotes"):
            self.assertRegex(text, resource + r"\s+2")

    def test_html_replay_reports_the_same_summary_fields_without_authentication(self):
        stdout = io.StringIO()
        with (
            patch("grove.downloaders.auth.resolve_cookies") as auth,
            patch("grove.downloaders.http.DataFetcher.fetch_html") as network,
            redirect_stdout(stdout),
            redirect_stderr(io.StringIO()),
        ):
            cli.main(self.html_command())
        auth.assert_not_called()
        network.assert_not_called()
        text = stdout.getvalue()
        for expected in (
            "HTML download complete",
            "Output",
            "Files",
            "Total records",
            "Elapsed",
            "Validation",
            "Passed: table completeness",
            "html_manifest.json",
        ):
            self.assertIn(expected, text)
        self.assertRegex(text, r"Total records\s+8")
        for resource in ("analyses", "papers", "confnotes", "pubnotes"):
            self.assertRegex(text, resource + r"\s+2")
            self.assertIn(resource + ".csv", text)
        self.assertNotIn("Invented content", text)

    def test_api_auth_validation_and_write_failures_report_preserved_output(self):
        destination = self.root / "api.json"
        for failure in ("authentication", "count_drop", "write"):
            with self.subTest(failure=failure):
                self.seed_api(destination, count=2 if failure == "count_drop" else 1)
                before = destination.read_bytes()
                stdout = io.StringIO()
                with (
                    patch("stare.Glance") as glance,
                    patch("stare.auth.TokenManager") as auth,
                    patch("stare.settings.StareSettings") as settings,
                    patch("grove.downloaders.api.atomic_write_text") as write,
                    self.assertLogs("grove", level="ERROR") as logs,
                    redirect_stdout(stdout),
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as error,
                ):
                    settings.return_value.base_url = "https://example.test/api"
                    glance.return_value.__enter__.return_value = client_for(1)
                    if failure == "authentication":
                        auth.side_effect = RuntimeError("synthetic-secret")
                    if failure == "write":
                        write.side_effect = OSError("disk full")
                    cli.main(["download-api", "--output", str(destination)])
                self.assertEqual(error.exception.code, 1)
                text = "\n".join(logs.output)
                self.assertIn("API download failed after", text)
                self.assertIn("previous download output preserved byte-for-byte", text)
                self.assertIn("Recovery files: none found", text)
                self.assertNotIn("synthetic-secret", text)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(destination.read_bytes(), before)

    def test_html_rollback_success_and_failure_are_distinguished(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            cli.main(self.html_command())
        original = {path.name: path.read_bytes() for path in self.csv_dir.iterdir()}
        analyses = self.saved / "analyses.html"
        analyses.write_text(
            analyses.read_text().replace("Invented content", "Changed content")
        )
        replace = Path.replace
        for rollback_fails in (False, True):

            def fail(source, target, rollback_fails=rollback_fails):
                if (
                    source.name == "papers.csv"
                    and source.parent.name != "previous"
                    or rollback_fails
                    and source.parent.name == "previous"
                ):
                    raise OSError("injected write failure")
                return replace(source, target)

            with (
                self.subTest(rollback_fails=rollback_fails),
                patch.object(Path, "replace", fail),
                self.assertLogs("grove", level="ERROR") as logs,
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                cli.main(self.html_command())
            text = "\n".join(logs.output)
            self.assertIn("HTML download failed after", text)
            if rollback_fails:
                self.assertIn("incomplete HTML batch", text)
                self.assertIn("Recovery files retained:", text)
                self.assertNotIn("output preserved", text)
                self.assertTrue((self.csv_dir / CSV_REFRESH_MARKER).exists())
                self.assertTrue(
                    list(self.csv_dir.glob(".refresh-*/previous/analyses.csv"))
                )
            else:
                self.assertIn("previous download output preserved byte-for-byte", text)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in self.csv_dir.iterdir()},
                    original,
                )

    def test_first_failure_and_post_publication_failure_do_not_claim_preservation(self):
        destination = self.root / "api.json"
        for writes_first in (False, True):

            def fail(writes_first=writes_first):
                if writes_first:
                    destination.write_text("published before cleanup failure")
                raise OSError("failed")

            with (
                self.subTest(writes_first=writes_first),
                self.assertLogs("grove.downloaders.reporting", level="ERROR") as logs,
                self.assertRaises(OSError),
            ):
                run_download(
                    fail,
                    kind="API",
                    destination=destination,
                    files=[destination],
                    validation="unused",
                    recovery_dir=self.root,
                    recovery_pattern=".api.json.*.tmp",
                )
            text = "\n".join(logs.output)
            self.assertIn(
                "files differ from their pre-download state"
                if writes_first
                else "no new download output published",
                text,
            )
            self.assertNotIn("output preserved", text)

    def test_unreadable_state_and_existing_interruption_are_not_reported_as_safe(self):
        destination = self.root / "api.json"
        with (
            patch(
                "grove.downloaders.reporting._file_state",
                return_value=("unknown", None),
            ),
            self.assertLogs("grove.downloaders.reporting", level="ERROR") as logs,
            self.assertRaises(ValueError),
        ):
            run_download(
                lambda: (_ for _ in ()).throw(ValueError("failure")),
                kind="API",
                destination=destination,
                files=[destination],
                validation="unused",
                recovery_dir=self.root,
                recovery_pattern=".api.json.*.tmp",
            )
        self.assertIn("could not verify", "\n".join(logs.output))
        self.csv_dir.mkdir()
        (self.csv_dir / CSV_REFRESH_MARKER).touch()
        (self.saved / "analyses.html").unlink()
        with (
            self.assertLogs("grove", level="ERROR") as logs,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            cli.main(self.html_command())
        self.assertIn("incomplete HTML batch", "\n".join(logs.output))
        self.assertNotIn("output preserved", "\n".join(logs.output))

    def test_output_read_errors_do_not_mask_the_download_failure_or_claim_safety(self):
        destination = self.root / "api.json"
        destination.write_bytes(b"previous synthetic output\n")
        before = destination.read_bytes()
        open_file = Path.open
        for fail_after_operation in (False, True):
            failure = ValueError("original download failure")
            operation = Mock(side_effect=failure)

            def unreadable(
                path,
                *args,
                operation=operation,
                fail_after_operation=fail_after_operation,
                **kwargs,
            ):
                if path == destination and operation.called == fail_after_operation:
                    raise PermissionError("synthetic-sensitive-read-error")
                return open_file(path, *args, **kwargs)

            with (
                self.subTest(fail_after_operation=fail_after_operation),
                patch.object(Path, "open", unreadable),
                self.assertLogs("grove", level="ERROR") as logs,
                self.assertRaises(ValueError) as raised,
            ):
                run_download(
                    operation,
                    kind="API",
                    destination=destination,
                    files=[destination],
                    validation="unused",
                    recovery_dir=self.root,
                    recovery_pattern=".api.json.*.tmp",
                )
            self.assertIs(raised.exception, failure)
            operation.assert_called_once_with()
            text = "\n".join(logs.output)
            self.assertIn("could not verify all output files", text)
            self.assertNotIn("output preserved", text)
            self.assertNotIn("no new download output", text)
            self.assertNotIn("synthetic-sensitive-read-error", text)
            self.assertEqual(destination.read_bytes(), before)

    def test_unreadable_interruption_marker_preserves_the_original_failure(self):
        self.csv_dir.mkdir()
        destination = self.csv_dir / "analyses.csv"
        destination.write_bytes(b"previous synthetic CSV\n")
        before = destination.read_bytes()
        marker = self.csv_dir / CSV_REFRESH_MARKER
        marker.touch()
        exists = Path.exists
        failure = ValueError("original download failure")

        def unreadable(path, *args, **kwargs):
            if path == marker:
                raise PermissionError("synthetic-sensitive-marker-error")
            return exists(path, *args, **kwargs)

        with (
            patch.object(Path, "exists", unreadable),
            self.assertLogs("grove", level="ERROR") as logs,
            self.assertRaises(ValueError) as raised,
        ):
            run_download(
                Mock(side_effect=failure),
                kind="HTML",
                destination=self.csv_dir,
                files=[destination],
                validation="unused",
                marker=marker,
                recovery_dir=self.csv_dir,
                recovery_pattern=".refresh-*/previous/*",
                saved_html=self.saved,
            )
        self.assertIs(raised.exception, failure)
        text = "\n".join(logs.output)
        self.assertIn("unable to inspect the HTML interruption marker", text)
        self.assertIn("verify the batch before use", text)
        self.assertIn(f"Saved diagnostic HTML may be partial: {self.saved}", text)
        self.assertNotIn("output preserved", text)
        self.assertNotIn("no new download output", text)
        self.assertNotIn("synthetic-sensitive-marker-error", text)
        self.assertTrue(marker.exists())
        self.assertEqual(destination.read_bytes(), before)

    def test_recovery_scan_errors_do_not_mask_the_original_failure(self):
        destination = self.root / "api.json"
        recovery = self.root / ".api.json.retained.tmp"
        recovery.write_bytes(b"retained synthetic recovery data\n")
        before = recovery.read_bytes()
        failure = ValueError("original download failure")

        def interrupted_scan(path, pattern):
            self.assertEqual((path, pattern), (self.root, ".api.json.*.tmp"))
            yield recovery
            raise OSError("synthetic-sensitive-scan-error")

        with (
            patch.object(Path, "glob", interrupted_scan),
            self.assertLogs("grove", level="ERROR") as logs,
            self.assertRaises(ValueError) as raised,
        ):
            run_download(
                Mock(side_effect=failure),
                kind="API",
                destination=destination,
                files=[destination],
                validation="unused",
                recovery_dir=self.root,
                recovery_pattern=".api.json.*.tmp",
            )
        self.assertIs(raised.exception, failure)
        text = "\n".join(logs.output)
        self.assertIn(f"Recovery files: unable to inspect {self.root}", text)
        self.assertNotIn("Recovery files: none found", text)
        self.assertNotIn("synthetic-sensitive-scan-error", text)
        self.assertEqual(recovery.read_bytes(), before)
        self.assertFalse(destination.exists())
