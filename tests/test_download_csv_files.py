# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline regression tests for the authenticated download boundary."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister.downloaders import http as downloader


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_default_bundle_contains_roots_and_intermediate_and_is_removed(self):
        with downloader.trusted_ca_bundle() as filename:
            path = Path(filename)
            content = path.read_bytes()
            self.assertIn(Path(requests.certs.where()).read_bytes(), content)
            self.assertIn(downloader.INTERMEDIATE_CA.read_bytes(), content)
        self.assertFalse(path.exists())

    def test_bundle_environment_overrides(self):
        for variable in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            with (
                self.subTest(variable=variable),
                patch.dict(os.environ, {variable: "/custom/ca.pem"}, clear=True),
                downloader.trusted_ca_bundle() as filename,
            ):
                self.assertEqual(filename, "/custom/ca.pem")

    def test_requests_override_takes_precedence(self):
        with (
            patch.dict(
                os.environ,
                {"REQUESTS_CA_BUNDLE": "/requests.pem", "CURL_CA_BUNDLE": "/curl.pem"},
            ),
            downloader.trusted_ca_bundle() as filename,
        ):
            self.assertEqual(filename, "/requests.pem")

    @patch.object(downloader.requests, "get")
    def test_success_uses_verified_tls_and_bounded_timeouts(self, get):
        def respond(url, **kwargs):
            self.assertEqual(url, "https://example.test")
            self.assertTrue(Path(kwargs["verify"]).is_file())
            self.assertEqual(kwargs["timeout"], (10, 30))
            self.assertEqual(kwargs["cookies"], {"session": "test"})
            self.assertEqual(kwargs["params"], {"table": "analyses"})
            return Mock(text="<table>result</table>")

        get.side_effect = respond
        result = downloader.DataFetcher.fetch_html(
            "https://example.test", {"table": "analyses"}, {"session": "test"}
        )
        self.assertEqual(result, "<table>result</table>")
        get.assert_called_once()

    @patch.object(downloader.requests, "get")
    def test_network_errors_propagate_without_insecure_retry(self, get):
        for error in (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
        ):
            with self.subTest(error=error):
                get.reset_mock()
                get.side_effect = error("test failure")
                with (
                    self.assertLogs(
                        "analysis_lister.downloaders.http", level="ERROR"
                    ) as logs,
                    self.assertRaises(error),
                ):
                    downloader.DataFetcher.fetch_html("https://example.test", {}, {})
                self.assertEqual(len(logs.output), 1)
                self.assertIn("https://example.test", logs.output[0])
                if error is requests.exceptions.SSLError:
                    self.assertIn("TLS verification failed", logs.output[0])
                else:
                    self.assertIn("test failure", logs.output[0])
                get.assert_called_once()
                self.assertFalse(Path(get.call_args.kwargs["verify"]).exists())

    @patch.object(downloader.requests, "get")
    def test_http_error_propagates(self, get):
        get.return_value.raise_for_status.side_effect = requests.HTTPError("503")
        with (
            self.assertLogs("analysis_lister.downloaders.http", level="ERROR") as logs,
            self.assertRaises(requests.HTTPError),
        ):
            downloader.DataFetcher.fetch_html("https://example.test", {}, {})
        self.assertIn("503", logs.output[0])

    @patch.object(downloader.requests, "get")
    def test_expired_session_is_rejected(self, get):
        get.return_value.text = "Sign in to your account"
        with self.assertRaisesRegex(ValueError, "Invalid or expired cookies"):
            downloader.DataFetcher.fetch_html("https://example.test", {}, {})


if __name__ == "__main__":
    unittest.main()
