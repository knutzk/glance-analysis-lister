# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Capture documentation images from the public synthetic Zensical site."""

import argparse
import base64
import functools
import math
import os
import struct
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
        pages = []
        for page in ("ongoing", "papers"):
            if pages:
                driver.switch_to.new_window("tab")
            driver.get(base + f"analyses/{page}/")
            wait.until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR, "[data-gal-count]"
                ).text.startswith("4 of 4")
            )
            record = (
                "#analysis-demo-ana-demo-2099-01"
                if page == "ongoing"
                else "#publication-papers-demo-demo-2099-01"
            )
            toggle = (
                "[data-gal-card-toggle]"
                if page == "ongoing"
                else "[data-gal-paper-toggle]"
            )
            # The gallery shows all four analysis cards and one paper's details.
            # Expanded analysis details are captured separately below.
            if page == "papers":
                driver.find_element(By.CSS_SELECTOR, f"{record} {toggle}").click()
                wait.until(
                    lambda d, record=record, toggle=toggle: (
                        d.find_element(
                            By.CSS_SELECTOR, f"{record} {toggle}"
                        ).get_attribute("aria-expanded")
                        == "true"
                    )
                )
            driver.execute_async_script(
                "const done = arguments[0]; document.fonts.ready.then(() => "
                "requestAnimationFrame(() => requestAnimationFrame(done)));"
            )
            collection = driver.find_element(By.CSS_SELECTOR, ".gal-collection")
            pages.append(
                (
                    page,
                    driver.current_window_handle,
                    record,
                    toggle,
                    collection,
                    collection.rect,
                )
            )

        # Both gallery images start at the filters and contain the full collection.
        # Give the shorter collection extra space below its records so the frames
        # match without stretching the image or including the provenance footer.
        width = math.ceil(max(bounds["width"] for *_, bounds in pages))
        height = math.ceil(max(bounds["height"] for *_, bounds in pages))
        padding = 8  # Retain card shadows and rounded filter borders.
        for page, handle, record, toggle, collection, _ in pages:
            driver.switch_to.window(handle)
            assert math.ceil(collection.rect["width"]) == width
            driver.execute_script(
                "arguments[0].style.minHeight = arguments[1] + 'px';",
                collection,
                height,
            )
            bounds = collection.rect
            screenshot = driver.execute_cdp_cmd(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport": True,
                    "clip": {
                        "x": math.floor(bounds["x"]) - padding,
                        "y": math.floor(bounds["y"]) - padding,
                        "width": width + 2 * padding,
                        "height": height + 2 * padding,
                        "scale": 1,
                    },
                },
            )
            image = base64.b64decode(screenshot["data"])
            dimensions = struct.unpack(">II", image[16:24])
            assert dimensions == (width + 2 * padding, height + 2 * padding)
            (destination / f"{page}.png").write_bytes(image)
            print(f"Captured docs/images/{page}.png ({dimensions[0]}×{dimensions[1]})")

            driver.execute_script("arguments[0].style.minHeight = '';", collection)
            if page == "ongoing":
                driver.find_element(By.CSS_SELECTOR, f"{record} {toggle}").click()
                wait.until(
                    lambda d, record=record, toggle=toggle: (
                        d.find_element(
                            By.CSS_SELECTOR, f"{record} {toggle}"
                        ).get_attribute("aria-expanded")
                        == "true"
                    )
                )
            content = driver.find_element(By.CSS_SELECTOR, ".md-content")
            driver.set_window_size(1440, int(content.rect["height"]) + 250)
            selector, filename = (
                (record, "ongoing-card")
                if page == "ongoing"
                else (".gal-table-scroll", "publication-row")
            )
            if page == "papers":
                # Keep the explanatory capture focused on the documented paper.
                driver.execute_script(
                    "const row = document.querySelector(arguments[0]);"
                    "for (const other of row.parentElement.children) {"
                    "if (other !== row && other !== row.nextElementSibling) "
                    "other.style.display = 'none';}",
                    record,
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
