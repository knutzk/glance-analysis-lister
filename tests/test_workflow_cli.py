"""Check executable boundaries separately from reusable workflow operations."""

import importlib
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
    import download_csv_files
    import refresh_analysis_lists
    import update_glance_registry
assert "selenium" not in sys.modules
assert "bs4" not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_download_flags_and_defaults_reach_workflows(self):
        for name, operation in (
            ("download_csv_files", "refresh_csv_files"),
            ("refresh_analysis_lists", "refresh_analysis_lists"),
        ):
            module = importlib.import_module(name)
            with (
                self.subTest(command=name),
                patch.object(module, "configure_logging"),
                patch.object(
                    module, "download_options", return_value={"cookies": {}}
                ) as auth,
                patch.object(module, operation) as workflow,
            ):
                flags = ["--debug", "--generate-new-cookies"]
                if name == "refresh_analysis_lists":
                    flags.append("--force")
                module.main(flags)
                auth.assert_called_once_with(
                    cli.COOKIE_FILE,
                    debug=True,
                    generate_new_cookies=True,
                    use_local_html=False,
                )
                if name == "refresh_analysis_lists":
                    workflow.assert_called_once_with(
                        cli.CSV_DIR,
                        cli.DEBUG_DIR,
                        cli.SNAPSHOT_PATH,
                        force=True,
                        cookies={},
                    )
                else:
                    workflow.assert_called_once_with(
                        download.download_tasks(cli.CSV_DIR),
                        cli.CSV_DIR,
                        cli.DEBUG_DIR,
                        cookies={},
                    )

    def test_registry_command_forwards_force(self):
        module = importlib.import_module("update_glance_registry")
        with (
            patch.object(module, "configure_logging"),
            patch.object(module, "update_registry") as workflow,
        ):
            module.main(["--force"])
        workflow.assert_called_once_with(cli.CSV_DIR, cli.SNAPSHOT_PATH, force=True)

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

    def test_executables_support_help_and_report_failures_without_tracebacks(self):
        with TemporaryDirectory() as directory:
            for name in (
                "download_csv_files",
                "refresh_analysis_lists",
                "update_glance_registry",
            ):
                for flags, expected_code in (
                    (["--help"], 0),
                    (
                        ["--use-local-html"]
                        if name != "update_glance_registry"
                        else [],
                        1,
                    ),
                ):
                    with self.subTest(command=name, flags=flags):
                        result = subprocess.run(
                            [sys.executable, str(SCRIPTS / f"{name}.py"), *flags],
                            cwd=directory,
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(
                            result.returncode, expected_code, result.stderr
                        )
                        self.assertNotIn("Traceback", result.stderr)
                        if expected_code:
                            self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
