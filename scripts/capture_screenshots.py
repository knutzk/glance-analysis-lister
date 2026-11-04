# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Capture documentation images from the public synthetic Zensical site."""

import argparse
import functools
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/browser"))
from check_zensical import SiteHandler, browse, build_site  # noqa: E402


def capture(base, driver_path):
    options = Options()
    if chrome := os.environ.get("CHROME_BINARY"):
        options.binary_location = chrome
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--disable-background-networking")
    destination = ROOT / "docs/images"
    destination.mkdir(parents=True, exist_ok=True)
    with webdriver.Chrome(options=options, service=Service(str(driver_path))) as driver:
        wait = WebDriverWait(driver, 15)
        for page in ("ongoing", "papers"):
            driver.get(base + f"analyses/{page}/")
            wait.until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR, "[data-gal-count]"
                ).text.startswith("1 of 1")
            )
            expand = (
                "[data-gal-expand-all]"
                if page == "ongoing"
                else "[data-gal-archive-expand-all]"
            )
            driver.find_element(By.CSS_SELECTOR, expand).click()
            wait.until(
                lambda d, expand=expand: (
                    d.find_element(By.CSS_SELECTOR, expand).get_attribute(
                        "aria-pressed"
                    )
                    == "true"
                )
            )
            driver.execute_async_script(
                "const done = arguments[0]; document.fonts.ready.then(() => "
                "requestAnimationFrame(() => requestAnimationFrame(done)));"
            )
            content = driver.find_element(By.CSS_SELECTOR, ".md-content")
            driver.set_window_size(1440, int(content.rect["height"]) + 250)
            assert content.screenshot(str(destination / f"{page}.png"))
            print(f"Captured docs/images/{page}.png")
            selector, filename = (
                (".gal-card", "ongoing-card")
                if page == "ongoing"
                else (".gal-table-scroll", "publication-row")
            )
            detail = driver.find_element(By.CSS_SELECTOR, selector)
            assert detail.screenshot(str(destination / f"{filename}.png"))
            print(f"Captured docs/images/{filename}.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="glance-screenshots-") as directory:
        work = Path(directory)
        with ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(SiteHandler, directory=str(work / "site")),
        ) as server:
            base = f"http://127.0.0.1:{server.server_port}/"
            build_site(work, base)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                browse(base, args.driver)
                capture(base, args.driver)
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    main()
