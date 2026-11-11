# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Failure capture must preserve the failing check and survive broken sessions."""

import importlib.util
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "browser_diagnostics", Path(__file__).parent / "browser/diagnostics.py"
)
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


class BrowserDiagnosticsTests(unittest.TestCase):
    def test_failure_is_captured_before_quit_and_reraised(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            driver = Mock(
                current_url="about:blank", capabilities={"browserVersion": "synthetic"}
            )
            driver.get_log.return_value = [{"level": "SEVERE", "message": "invented"}]

            def screenshot(path):
                driver.quit.assert_not_called()
                Path(path).write_bytes(b"invented screenshot")

            driver.save_screenshot.side_effect = screenshot
            with (  # noqa: SIM117 - keep the failing operation inside its assertion
                patch.dict(os.environ, BROWSER_DIAGNOSTICS_DIR=str(root)),
                patch.object(diagnostics.webdriver, "Chrome", return_value=driver),
                patch.object(diagnostics, "Service"),
            ):
                with self.assertRaisesRegex(AssertionError, "original failure"):
                    with diagnostics.chrome(
                        options=Mock(), driver_path="unused", label="test"
                    ):
                        raise AssertionError("original failure")
            (report,) = root.iterdir()
            self.assertTrue((report / "failure.png").is_file())
            self.assertIn("invented", (report / "browser.json").read_text())
            self.assertIn("original failure", (report / "failure.txt").read_text())
            driver.quit.assert_called_once()

    def test_broken_capture_and_cleanup_preserve_original_failure(self):
        with TemporaryDirectory() as temporary:
            driver = Mock()
            driver.save_screenshot.side_effect = RuntimeError("browser gone")
            driver.get_log.side_effect = RuntimeError("browser gone")
            driver.quit.side_effect = RuntimeError("quit failed")
            with (  # noqa: SIM117 - keep the failing operation inside its assertion
                patch.dict(os.environ, BROWSER_DIAGNOSTICS_DIR=temporary),
                patch.object(diagnostics.webdriver, "Chrome", return_value=driver),
                patch.object(diagnostics, "Service"),
            ):
                with self.assertRaisesRegex(AssertionError, "original failure"):
                    with diagnostics.chrome(options=Mock(), driver_path="unused"):
                        raise AssertionError("original failure")
            (report,) = Path(temporary).iterdir()
            errors = (report / "capture-errors.txt").read_text()
            self.assertIn("browser gone", errors)
            self.assertIn("quit failed", errors)

    def test_startup_failure_retains_driver_log(self):
        with TemporaryDirectory() as temporary:

            def service(*args, log_output):
                Path(log_output).write_text("invented startup failure")
                return Mock()

            with (  # noqa: SIM117 - keep the failing operation inside its assertion
                patch.dict(os.environ, BROWSER_DIAGNOSTICS_DIR=temporary),
                patch.object(diagnostics, "Service", side_effect=service),
                patch.object(
                    diagnostics.webdriver,
                    "Chrome",
                    side_effect=RuntimeError("startup failed"),
                ),
                self.assertRaisesRegex(RuntimeError, "startup failed"),
            ):
                with diagnostics.chrome(options=Mock(), driver_path="unused"):
                    self.fail("must not enter")
            (report,) = Path(temporary).iterdir()
            self.assertIn("invented", (report / "chromedriver.log").read_text())

    def test_success_does_not_retain_artifacts(self):
        with TemporaryDirectory() as temporary:
            with (  # noqa: SIM117 - keep the failing operation inside its assertion
                patch.dict(os.environ, BROWSER_DIAGNOSTICS_DIR=temporary),
                patch.object(diagnostics.webdriver, "Chrome"),
                patch.object(diagnostics, "Service"),
            ):
                with diagnostics.chrome(options=Mock(), driver_path="unused"):
                    pass
            self.assertEqual(list(Path(temporary).iterdir()), [])
