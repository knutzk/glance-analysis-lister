# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Actionable CLI failures without exposing synthetic credentials or payloads."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import requests
from stare.exceptions import (
    ApiError,
    AuthenticationError,
    NetworkError,
    ResponseParseError,
    TokenExpiredError,
)
from test_api import client_for

from grove import cli
from grove.downloaders.html import download_tasks
from grove.downloaders.manifest import HTML_MANIFEST, make_manifest

SECRET = "invented-sensitive-marker"
URL = f"https://{SECRET}:{SECRET}@example.test/api?token={SECRET}#{SECRET}"


class DownloadErrorTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "api.json"
        self.output.write_bytes(b"previous synthetic output\n")
        self.before = self.output.read_bytes()
        self.enterContext(
            patch(
                "socket.socket.connect",
                side_effect=AssertionError("unexpected network"),
            )
        )

    def failure(self, command, expected, mode):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            cli.main([*command, *mode, "--color", "never"])
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn(SECRET, stderr.getvalue())
        text = " ".join(stderr.getvalue().split())
        self.assertIn(expected, text)
        return text

    def api_failure(self, client, expected, mode, *, stage=None, error=None):
        with (
            patch("stare.Glance") as glance,
            patch("stare.auth.TokenManager") as auth,
            patch("stare.settings.StareSettings") as settings,
        ):
            settings.return_value.base_url = URL
            glance.return_value.__enter__.return_value = client
            if stage == "configuration":
                settings.side_effect = error
            elif stage == "authentication":
                auth.side_effect = error
            text = self.failure(
                ["download-api", "--output", str(self.output), "--page-size", "2"],
                expected,
                mode,
            )
        self.assertEqual(self.output.read_bytes(), self.before)
        self.assertIn("previous download output preserved byte-for-byte", text)
        self.assertNotIn("download complete", text)

    def test_api_upstream_errors_have_distinct_safe_remedies(self):
        cases = (
            (AuthenticationError(SECRET), "Authentication failed", "authentication"),
            (TokenExpiredError(SECRET), "retry with --login", None),
            (
                ApiError(401, SECRET, SECRET),
                "HTTP 401: authentication was rejected",
                None,
            ),
            (ApiError(403, SECRET, SECRET), "HTTP 403: access was denied", None),
            (ApiError(404, SECRET, SECRET), "HTTP 404: endpoint was not found", None),
            (ApiError(429, SECRET, SECRET), "HTTP 429: request rate was limited", None),
            (ApiError(503, SECRET, SECRET), "HTTP 503: service failed", None),
            (NetworkError(SECRET), "Network request failed", None),
            (
                ResponseParseError(SECRET, raw_data={"title": SECRET}),
                "Response validation failed",
                None,
            ),
            (
                json.JSONDecodeError(SECRET, SECRET, 0),
                "analyses: invalid JSON or model fields",
                None,
            ),
            (RuntimeError(SECRET), "Client configuration failed", "configuration"),
            (RuntimeError(SECRET), "Unexpected retrieval failure", None),
        )
        for error, expected, stage in cases:
            # Upstream transport/model errors often carry a second sensitive exception.
            error.__cause__ = ValueError(SECRET)
            for mode in ([], ["--quiet"], ["--verbose"]):
                with self.subTest(
                    error=type(error).__name__, expected=expected, mode=mode
                ):
                    client = client_for()
                    client.analyses.search.side_effect = error
                    self.api_failure(client, expected, mode, stage=stage, error=error)

    def test_pagination_and_record_errors_keep_resource_and_reason(self):
        for case, expected in (
            ("duplicate", "Pagination failed: analyses: duplicate record across pages"),
            ("changed", "Pagination failed: analyses: count changed during pagination"),
            ("truncated", "Pagination failed: analyses: incomplete or invalid page"),
            ("empty", "Pagination failed: analyses: empty or invalid result count"),
            (
                "identity",
                "Response validation failed: analyses: invalid record or missing native identifier",
            ),
        ):
            for mode in ([], ["--quiet"], ["--verbose"]):
                with self.subTest(case=case, mode=mode):
                    client = client_for(4)
                    first = client.analyses.search(offset=0, limit=2)
                    if case == "duplicate":
                        client.analyses.search.side_effect = [first, first]
                    elif case == "changed":
                        client.analyses.search.side_effect = [
                            first,
                            SimpleNamespace(number_of_results=5, results=[]),
                        ]
                    elif case == "truncated":
                        client.analyses.search.side_effect = [
                            first,
                            SimpleNamespace(number_of_results=4, results=[]),
                        ]
                    elif case == "empty":
                        client.analyses.search.return_value = SimpleNamespace(
                            number_of_results=0, results=[]
                        )
                        client.analyses.search.side_effect = None
                    else:
                        first.results[0].model_dump.return_value = {"title": SECRET}
                    self.api_failure(client, expected, mode)

    def test_html_transport_errors_hide_exception_text_and_urls(self):
        destination = self.root / "csv"
        destination.mkdir()
        tasks = download_tasks()
        for task in tasks:
            (destination / task.csv_filename).write_bytes(self.before)
        (destination / HTML_MANIFEST).write_text(json.dumps(make_manifest(tasks)))
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        for error, expected in (
            (requests.exceptions.SSLError(SECRET), "TLS verification failed"),
            (requests.ConnectTimeout(SECRET), "Request timed out"),
            (requests.ReadTimeout(SECRET), "Request timed out"),
            (requests.ConnectionError(SECRET), "Connection failed"),
            (requests.RequestException(SECRET), "Request failed"),
            *[
                (
                    requests.HTTPError(SECRET, response=self.response(status)),
                    f"HTTP {status}",
                )
                for status in (401, 403, 404, 429, 503)
            ],
        ):
            for mode in ([], ["--quiet"], ["--verbose"]):
                with self.subTest(
                    error=type(error).__name__, expected=expected, mode=mode
                ):
                    with (
                        patch(
                            "grove.downloaders.auth.resolve_cookies",
                            return_value={"session": SECRET},
                        ),
                        patch.dict(
                            "grove.downloaders.http.URLS",
                            {task.name: URL for task in tasks},
                        ),
                        patch(
                            "grove.downloaders.http.requests.get",
                            side_effect=error,
                        ) as get,
                    ):
                        text = self.failure(
                            ["download-html", "--csv-dir", str(destination)],
                            expected,
                            mode,
                        )
                    get.assert_called_once()
                    self.assertIn("https://example.test/api", text)
                    self.assertIn(
                        "previous download output preserved byte-for-byte", text
                    )
                    self.assertEqual(
                        {
                            path.name: path.read_bytes()
                            for path in destination.iterdir()
                        },
                        before,
                    )

    @staticmethod
    def response(status):
        response = requests.Response()
        response.status_code = status
        response.url = URL
        response._content = SECRET.encode()
        return response

    def test_curated_schema_cli_error_shows_field_path_without_values(self):
        source = (
            Path(__file__).resolve().parents[1] / "examples/synthetic_registry.json"
        )
        data = json.loads(source.read_text())
        data["papers"][0]["shortTitle"] = {"private": SECRET}
        snapshot = self.root / "curated.json"
        snapshot.write_text(json.dumps(data))
        pages = self.root / "pages"
        pages.mkdir()
        existing = pages / "ongoing.md"
        existing.write_text("previous synthetic page")
        for mode in ([], ["--quiet"], ["--verbose"]):
            with self.subTest(mode=mode):
                self.failure(
                    [
                        "render-group",
                        "--group",
                        "DEMO",
                        "--snapshot",
                        str(snapshot),
                        "--output-dir",
                        str(pages),
                    ],
                    "Curated registry $.papers[0].shortTitle",
                    mode,
                )
                self.assertEqual(existing.read_text(), "previous synthetic page")
                self.assertEqual(list(pages.iterdir()), [existing])
