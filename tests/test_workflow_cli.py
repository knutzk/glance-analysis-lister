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
from analysis_lister.downloaders import html as download

SCRIPTS = Path(__file__).resolve().parents[1]


class WorkflowCliTests(unittest.TestCase):
    def test_imports_do_not_configure_logging_or_load_browser_dependencies(self):
        code = """
import logging
import sys
from unittest.mock import patch
with patch.object(logging, "basicConfig", side_effect=AssertionError("logging on import")):
    import analysis_lister.cli
    import analysis_lister.downloaders.publication
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
            patch.object(download, "resolve_cookies", return_value={}) as auth,
            patch(
                "analysis_lister.downloaders.publication.download_html_csvs"
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
        auth.assert_called_once_with(Path("session.json"), generate_new_cookies=True)
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
                patch.object(download, "resolve_cookies") as auth,
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                cli.main([command])
            self.assertEqual(error.exception.code, 2)
            auth.assert_not_called()

    def test_api_default_and_downloads_do_not_load_citations(self):
        with (
            patch(
                "analysis_lister.downloaders.api.download_registry", return_value={}
            ) as operation,
            patch("analysis_lister.citation_store.cached_citations") as citations,
        ):
            cli.main(["download-api"])
        operation.assert_called_once_with(
            cli.API_SNAPSHOT_PATH, login=False, allow_count_drop=False
        )
        citations.assert_not_called()
        parser = cli.parser()
        for command in ("download-api", "download-html"):
            self.assertFalse(hasattr(parser.parse_args([command]), "doi_cache"))

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
            doi_cache=Path("json/doi_metadata.json"),
        )

    def test_offline_cli_never_reads_credentials(self):
        with (
            patch.object(cli, "configure_logging"),
            patch.object(
                download.CookieManager,
                "load_cookies",
                side_effect=AssertionError("credentials read"),
            ),
            patch(
                "analysis_lister.downloaders.publication.download_html_csvs"
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
            download.CookieManager,
            "generate_cookies",
            return_value=[{"name": "session", "value": "synthetic"}],
        ) as generate:
            cookies = download.resolve_cookies(
                Path("session.json"), generate_new_cookies=True
            )
        generate.assert_called_once_with(Path("session.json"))
        self.assertEqual(cookies, {"session": "synthetic"})

    def test_cookie_path_is_supplied_by_caller(self):
        with TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "session.json"
            with self.assertRaisesRegex(ValueError, "No cookies found"):
                download.resolve_cookies(cookie_file)
            download.CookieManager.save_cookies(
                [{"name": "test", "value": "synthetic"}], cookie_file
            )
            self.assertEqual(
                download.resolve_cookies(cookie_file),
                {"test": "synthetic"},
            )


if __name__ == "__main__":
    unittest.main()
