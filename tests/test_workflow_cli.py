"""Check executable boundaries separately from reusable workflow operations."""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_lister import cli, download

SCRIPTS = Path(__file__).resolve().parents[1]


class WorkflowCliTests(unittest.TestCase):
    def test_imports_do_not_configure_logging_or_load_browser_dependencies(self):
        code = """
import logging
import sys
from unittest.mock import patch
with patch.object(logging, "basicConfig", side_effect=AssertionError("logging on import")):
    import analysis_lists
    import analysis_lister.refresh
    import analysis_lister.render
assert "selenium" not in sys.modules
assert "bs4" not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_download_flags_and_paths_reach_workflows(self):
        for name, operation in (
            ("download", "refresh_csv_files"),
            ("refresh", "refresh_analysis_lists"),
        ):
            with (
                self.subTest(command=name),
                patch.object(cli, "configure_logging"),
                patch.object(
                    download, "download_options", return_value={"cookies": {}}
                ) as auth,
                patch("analysis_lister.refresh." + operation) as workflow,
            ):
                flags = [
                    name,
                    "--save-html",
                    "html",
                    "--login",
                    "--cookies",
                    "session.json",
                    "--csv-dir",
                    "csv",
                ]
                if name == "refresh":
                    flags += ["--allow-count-drop", "--snapshot", "registry.json"]
                cli.main(flags)
                auth.assert_called_once_with(
                    Path("session.json"),
                    debug=True,
                    generate_new_cookies=True,
                    use_local_html=False,
                )
                if name == "refresh":
                    workflow.assert_called_once_with(
                        Path("csv"),
                        Path("html"),
                        Path("registry.json"),
                        force=True,
                        cookies={},
                    )
                else:
                    workflow.assert_called_once_with(
                        download.download_tasks(Path("csv")),
                        Path("csv"),
                        Path("html"),
                        cookies={},
                    )

    def test_registry_command_forwards_count_override(self):
        with (
            patch.object(cli, "configure_logging"),
            patch("analysis_lister.refresh.update_registry") as workflow,
        ):
            cli.main(["build-registry", "--allow-count-drop"])
        workflow.assert_called_once_with(cli.CSV_DIR, cli.SNAPSHOT_PATH, force=True)

    def test_offline_cli_never_reads_credentials(self):
        with (
            patch.object(cli, "configure_logging"),
            patch.object(
                download.CookieManager,
                "load_cookies",
                side_effect=AssertionError("credentials read"),
            ),
            patch("analysis_lister.refresh.refresh_analysis_lists") as workflow,
        ):
            cli.main(["refresh", "--from-html", "saved"])
        workflow.assert_called_once_with(
            cli.CSV_DIR,
            Path("saved"),
            cli.SNAPSHOT_PATH,
            force=False,
            use_local_html=True,
        )

    def test_invalid_combinations_fail_before_work_starts(self):
        for flags in (
            [],
            ["refresh", "--from-html", "saved", "--login"],
            ["download", "--from-html", "saved", "--save-html", "saved"],
            ["render", "--login"],
            ["download", "--allow-count-drop"],
            ["refresh", "--force"],
            ["download", "--debug"],
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

    def test_render_dispatches_explicit_paths(self):
        with (
            patch.object(cli, "configure_logging"),
            patch("analysis_lister.render.render_pages") as render,
        ):
            cli.main(["render", "--snapshot", "input.json", "--output-dir", "pages"])
        render.assert_called_once_with(Path("input.json"), Path("pages"))

    def test_offline_mode_ignores_cookie_generation_and_debug(self):
        with (
            patch.object(download.CookieManager, "generate_cookies") as generate,
            patch.object(download.CookieManager, "load_cookies") as load,
        ):
            options = download.download_options(
                Path("unused.json"),
                use_local_html=True,
                generate_new_cookies=True,
                debug=True,
            )
        self.assertEqual(options, {"use_local_html": True})
        generate.assert_not_called()
        load.assert_not_called()

    def test_cookie_path_is_supplied_by_caller(self):
        with TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "session.json"
            with self.assertRaisesRegex(ValueError, "No cookies found"):
                download.download_options(cookie_file)
            download.CookieManager.save_cookies(
                [{"name": "test", "value": "synthetic"}], cookie_file
            )
            self.assertEqual(
                download.download_options(cookie_file),
                {"cookies": {"test": "synthetic"}, "debug": False},
            )

    def test_executable_help_errors_and_lookup_validation(self):
        with TemporaryDirectory() as directory:
            cases = [(["--help"], 0), (["validate-lookups"], 0)]
            for command in (
                "refresh",
                "download",
                "build-registry",
                "render",
                "validate-lookups",
            ):
                cases.append(([command, "--help"], 0))
                flags = [command]
                if command in ("refresh", "download"):
                    flags += ["--from-html", "missing"]
                elif command == "validate-lookups":
                    flags += ["--snapshot", "missing.json"]
                cases.append((flags, 1))
            for flags, expected_code in cases:
                with self.subTest(flags=flags):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS / "analysis_lists.py"), *flags],
                        cwd=directory,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, expected_code, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    if expected_code:
                        self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
