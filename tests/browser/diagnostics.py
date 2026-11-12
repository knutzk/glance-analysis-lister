# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Retain only browser diagnostics from the synthetic checks on failure."""

import json
import os
import shutil
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


def capture(directory, name, operation):
    """A broken browser must not replace the original test failure."""
    try:
        operation()
    except Exception as error:
        with (directory / "capture-errors.txt").open("a") as stream:
            stream.write(f"{name}: {error}\n")


@contextmanager
def chrome(*, options, driver_path, label=None):
    """Capture evidence before quitting Chrome, including startup failures."""
    label = label or Path(sys.argv[0]).stem
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    with TemporaryDirectory(prefix="grove-browser-diagnostics-") as temporary:
        work = Path(temporary)
        service = Service(str(driver_path), log_output=str(work / "chromedriver.log"))
        driver = None
        failed = False
        try:
            driver = webdriver.Chrome(options=options, service=service)
            yield driver
        except BaseException:
            failed = True
            # Capture each item independently: crashed sessions may provide only logs.
            try:
                (work / "failure.txt").write_text(traceback.format_exc())
                if driver is not None:
                    capture(
                        work,
                        "screenshot",
                        lambda: driver.save_screenshot(str(work / "failure.png")),
                    )
                    capture(
                        work,
                        "browser log",
                        lambda: (work / "browser.json").write_text(
                            json.dumps(driver.get_log("browser"), indent=2)
                        ),
                    )
                    capture(
                        work,
                        "session",
                        lambda: (work / "session.json").write_text(
                            json.dumps(
                                {
                                    "url": driver.current_url,
                                    "capabilities": driver.capabilities,
                                },
                                indent=2,
                            )
                        ),
                    )
            except Exception as error:
                print(
                    f"Could not capture browser diagnostics: {error}", file=sys.stderr
                )
            raise
        finally:
            # Stop the service before copying its flushed log, even if startup failed.
            def stop():
                try:
                    if driver is not None:
                        driver.quit()
                finally:
                    service.stop()

            if failed:
                try:
                    capture(work, "cleanup", stop)
                    root = Path(
                        os.environ.get("BROWSER_DIAGNOSTICS_DIR", "browser-report")
                    )
                    root.mkdir(parents=True, exist_ok=True)
                    destination = Path(mkdtemp(prefix=f"{label}-", dir=root))
                    shutil.copytree(work, destination, dirs_exist_ok=True)
                    print(
                        f"Browser failure diagnostics: {destination}", file=sys.stderr
                    )
                except Exception as error:
                    print(
                        f"Could not save browser diagnostics: {error}", file=sys.stderr
                    )
            else:
                stop()
