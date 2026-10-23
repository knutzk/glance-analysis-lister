# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Terminal colour, readable diagnostics and isolated CLI logging."""

import io
import logging
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_lister import cli
from analysis_lister.console import (
    ConsoleFormatter,
    configure_logging,
    print_summary,
    use_color,
)

ROOT = Path(__file__).resolve().parents[1]


class Terminal(io.StringIO):
    def isatty(self):
        return True


class ConsoleTests(unittest.TestCase):
    def test_auto_color_requires_terminal_and_honours_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(use_color(Terminal()))
            self.assertFalse(use_color(io.StringIO()))
        for environment in ({"NO_COLOR": "1"}, {"NO_COLOR": ""}, {"TERM": "dumb"}):
            with patch.dict(os.environ, environment, clear=True):
                self.assertFalse(use_color(Terminal()))
                self.assertTrue(use_color(io.StringIO(), "always"))
                self.assertFalse(use_color(Terminal(), "never"))

    def test_formatter_colours_severity_and_aligns_wrapped_bullets(self):
        record = logging.LogRecord(
            "analysis_lister.demo",
            logging.WARNING,
            "",
            0,
            "2 notices:\n  - " + "A synthetic diagnostic needs attention. " * 3,
            (),
            None,
        )
        plain = ConsoleFormatter(width=60).format(record)
        colour = ConsoleFormatter(color=True, width=60).format(record)
        self.assertTrue(plain.startswith("WARN  2 notices:\n        - "))
        self.assertIn("\033[33mWARN ", colour)
        self.assertNotIn("\033[", plain)
        self.assertTrue(all(len(line) <= 60 for line in plain.splitlines()))
        self.assertEqual(
            record.getMessage(),
            "2 notices:\n  - " + "A synthetic diagnostic needs attention. " * 3,
        )

    def test_verbose_formatter_has_timestamp_module_and_traceback(self):
        try:
            raise ValueError("synthetic failure")
        except ValueError:
            record = logging.LogRecord(
                "analysis_lister.demo",
                logging.DEBUG,
                "",
                0,
                "Operation failed",
                (),
                sys.exc_info(),
            )
        text = ConsoleFormatter(verbose=True).format(record)
        self.assertRegex(text, r"^\d{2}:\d{2}:\d{2} DEBUG demo:")
        self.assertIn("ValueError: synthetic failure", text)

    def test_cli_handler_restores_host_logging_after_failure(self):
        logger = logging.getLogger("analysis_lister")
        root = logging.getLogger()
        previous = (
            logger.level,
            list(logger.handlers),
            list(root.handlers),
            root.level,
        )
        stream = io.StringIO()
        with (
            patch("sys.stderr", stream),
            self.assertRaises(ValueError),
            configure_logging(),
        ):
            logger.info("visible progress")
            logger.debug("hidden detail")
            raise ValueError("synthetic")
        self.assertIn("INFO  visible progress", stream.getvalue())
        self.assertNotIn("hidden detail", stream.getvalue())
        self.assertEqual(
            (logger.level, logger.handlers, root.handlers, root.level), previous
        )

    def test_quiet_keeps_warnings_and_results(self):
        stream, output = io.StringIO(), io.StringIO()
        with (
            patch("sys.stderr", stream),
            patch("sys.stdout", output),
            configure_logging(quiet=True),
        ):
            logger = logging.getLogger("analysis_lister.demo")
            logger.info("progress")
            logger.warning("needs attention")
            print_summary("Completed", [("Records", 12)])
        self.assertNotIn("progress", stream.getvalue())
        self.assertIn("WARN  needs attention", stream.getvalue())
        self.assertEqual(output.getvalue(), "Completed\n  Records  12\n")

    def test_logging_options_work_before_or_after_subcommand(self):
        for flags in (
            ["--verbose", "format-citations", "--color", "always"],
            ["--color", "always", "format-citations", "--verbose"],
        ):
            with (
                patch.object(cli, "configure_logging") as setup,
                patch.object(cli, "run"),
            ):
                cli.main(flags)
                setup.assert_called_once_with(verbose=True, quiet=False, color="always")
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--quiet", "format-citations", "--verbose"])
        self.assertEqual(error.exception.code, 2)

    def test_forced_colour_overrides_no_color_and_never_stays_plain(self):
        for mode in ("always", "never"):
            with (
                self.subTest(mode=mode),
                patch.dict(os.environ, {"NO_COLOR": "1"}),
                patch("sys.stdout", io.StringIO()) as output,
                patch("analysis_lister.doi_resolver.format_citations", return_value=0),
            ):
                cli.main(
                    [
                        "--color",
                        mode,
                        "format-citations",
                        "--doi-cache",
                        "/tmp/gal-console-empty-citations.json",
                    ]
                )
                self.assertEqual("\033[" in output.getvalue(), mode == "always")

    def test_redirected_cli_output_has_no_ansi_or_traceback_on_failure(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "analysis_lister",
                "render-group",
                "--group",
                "DEMO",
                "--snapshot",
                "missing-synthetic.json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("WARNING:", result.stdout)
        self.assertIn("ERROR", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("\033[", result.stderr)

    def test_subprocess_render_has_concise_progress_and_completion(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "analysis_lister",
                    "render-group",
                    "--group",
                    "DEMO",
                    "--snapshot",
                    str(ROOT / "examples/synthetic_registry.json"),
                    "--output-dir",
                    directory,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Group views rendered", result.stdout)
        self.assertNotIn("Writing output file", result.stderr)
        self.assertNotIn("\033[", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
