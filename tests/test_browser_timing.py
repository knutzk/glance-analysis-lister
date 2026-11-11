# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Timing output must not turn failed browser checks into successful runs."""

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "browser_timing", Path(__file__).parent / "browser/timing.py"
)
timing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timing)


class BrowserTimingTests(unittest.TestCase):
    def test_success_reports_elapsed_time(self):
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch.object(timing, "perf_counter", side_effect=[10, 12.345]),
            timing.timed("synthetic phase"),
        ):
            pass
        self.assertIn("[timing] START synthetic phase", output.getvalue())
        self.assertIn("[timing] PASS synthetic phase: 2.345s", output.getvalue())

    def test_failure_and_interruption_are_reported_and_preserved(self):
        for error in (AssertionError("check failed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                output = io.StringIO()
                with (
                    redirect_stdout(output),
                    self.assertRaises(type(error)) as caught,
                    timing.timed("synthetic phase"),
                ):
                    raise error
                self.assertIs(caught.exception, error)
                self.assertIn("[timing] FAIL synthetic phase:", output.getvalue())
                self.assertNotIn("[timing] PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
