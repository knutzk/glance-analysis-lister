# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Check executable boundaries separately from reusable workflow operations."""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister import cli
from analysis_lister.downloaders import auth, html as download

SCRIPTS = Path(__file__).resolve().parents[1]


class WorkflowCliTests(unittest.TestCase):
    def test_imports_do_not_configure_logging_or_load_browser_dependencies(self):
        code = """
import logging
import sys
from unittest.mock import patch
with patch.object(logging, "basicConfig", side_effect=AssertionError("logging on import")):
    import analysis_lister.cli
    import analysis_lister.downloaders.csv_batch
    import analysis_lister.views.build
assert "selenium" not in sys.modules
assert "bs4" not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_download_flags_and_paths_reach_workflows(self):
        with (
            patch.object(cli, "configure_logging"),
            patch.object(auth, "resolve_cookies", return_value={}) as credentials,
            patch(
                "analysis_lister.downloaders.csv_batch.download_html_csvs"
            ) as workflow,
        ):
            cli.main(
                [
                    "download-html",
                    "--save-html",
                    "html",
                    "--login",
                    "--cookies",
                    "session.json",
                    "--csv-dir",
                    "csv",
                ]
            )
        credentials.assert_called_once_with(
            Path("session.json"), generate_new_cookies=True
        )
        workflow.assert_called_once_with(
            download.download_tasks(),
            Path("csv"),
            Path("html"),
            cookies={},
            use_local_html=False,
            debug=True,
        )

    def test_removed_commands_fail_before_authentication(self):
        for command in (
            "refresh",
            "download",
            "render",
            "export-obsidian",
            "validate-lookups",
        ):
            with (
                self.subTest(command=command),
                patch.object(auth, "resolve_cookies") as credentials,
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main([command])
            self.assertEqual(error.exception.code, 2)
            credentials.assert_not_called()

    def test_api_default_and_downloads_do_not_load_citations(self):
        with (
            patch(
                "analysis_lister.downloaders.api.download_registry", return_value={}
            ) as operation,
            patch("analysis_lister.citations.store.cached_citations") as citations,
        ):
            cli.main(["download-api"])
        operation.assert_called_once_with(
            cli.API_SNAPSHOT_PATH, login=False, allow_count_drop=False, page_size=100
        )
        citations.assert_not_called()
        parser = cli.parser()
        for command in ("download-api", "download-html"):
            self.assertFalse(hasattr(parser.parse_args([command]), "doi_cache"))

    def test_api_page_size_is_forwarded_and_invalid_values_fail_before_auth(self):
        with patch(
            "analysis_lister.downloaders.api.download_registry", return_value={}
        ) as operation:
            cli.main(["download-api", "--page-size", "500"])
        self.assertEqual(operation.call_args.kwargs["page_size"], 500)
        for value in ("0", "-1", "1.5", "not-an-integer"):
            with (
                self.subTest(value=value),
                patch("stare.auth.TokenManager") as manager,
                patch("sys.stderr"),
                self.assertRaises(SystemExit),
            ):
                cli.main(["download-api", "--page-size", value])
            manager.assert_not_called()

    def test_json_defaults_are_relative_to_the_working_directory(self):
        parser = cli.parser()
        self.assertEqual(
            parser.parse_args(["download-api"]).output, Path("glance_api_registry.json")
        )
        build = parser.parse_args(["build-registry"])
        self.assertEqual(build.api_snapshot, Path("glance_api_registry.json"))
        self.assertEqual(build.output, Path("glance_curated_registry.json"))
        self.assertEqual(build.doi_cache, cli.default_store_path())
        self.assertEqual(
            parser.parse_args(["render-group", "--group", "DEMO"]).snapshot,
            build.output,
        )

    def test_registry_command_forwards_count_override(self):
        with (
            patch.object(cli, "configure_logging"),
            patch(
                "analysis_lister.registry.builder.build_registry", return_value={}
            ) as workflow,
        ):
            cli.main(["build-registry", "--allow-count-drop"])
        workflow.assert_called_once_with(
            cli.API_SNAPSHOT_PATH,
            cli.SUPPLEMENT_CSV_DIR,
            cli.CURATED_SNAPSHOT_PATH,
            allow_count_drop=True,
            doi_cache=cli.default_store_path(),
        )

    def test_offline_cli_never_reads_credentials(self):
        with (
            patch.object(cli, "configure_logging"),
            patch.object(
                auth.CookieManager,
                "load_cookies",
                side_effect=AssertionError("credentials read"),
            ),
            patch(
                "analysis_lister.downloaders.csv_batch.download_html_csvs"
            ) as workflow,
        ):
            cli.main(["download-html", "--from-html", "saved"])
        workflow.assert_called_once_with(
            download.download_tasks(),
            cli.SUPPLEMENT_CSV_DIR,
            Path("saved"),
            use_local_html=True,
            cookies=None,
            debug=False,
        )

    def test_invalid_combinations_fail_before_work_starts(self):
        for flags in (
            [],
            ["download-html", "--from-html", "saved", "--login"],
            ["download-html", "--from-html", "saved", "--save-html", "saved"],
            ["render", "--login"],
            ["download-html", "--allow-count-drop"],
            ["build-registry", "--force"],
            ["download-html", "--debug"],
            ["download-html", "--snapshot", "snapshot.json"],
            ["build-registry", "--output-dir", "pages"],
            ["render", "--allow-count-drop"],
            ["validate-lookups", "--csv-dir", "csv"],
        ):
            with (
                self.subTest(flags=flags),
                patch.object(cli, "run") as run,
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main(flags)
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_login_passes_cookie_path_and_returns_credentials(self):
        with patch.object(
            auth.CookieManager,
            "generate_cookies",
            return_value=[{"name": "session", "value": "synthetic"}],
        ) as generate:
            cookies = auth.resolve_cookies(
                Path("session.json"), generate_new_cookies=True
            )
        generate.assert_called_once_with(Path("session.json"))
        self.assertEqual(cookies, {"session": "synthetic"})

    def test_cookie_path_is_supplied_by_caller(self):
        with TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "session.json"
            with self.assertRaisesRegex(ValueError, "No cookies found"):
                auth.resolve_cookies(cookie_file)
            auth.CookieManager.save_cookies(
                [{"name": "test", "value": "synthetic"}], cookie_file
            )
            self.assertEqual(
                auth.resolve_cookies(cookie_file),
                {"test": "synthetic"},
            )


if __name__ == "__main__":
    unittest.main()
