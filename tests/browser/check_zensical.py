# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build and browse a synthetic Zensical site, including real instant navigation."""

import argparse
import functools
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from analysis_lister.views.build import render_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

ROOT = Path(__file__).resolve().parents[2]
PAGES = ("ongoing", "papers", "confnotes", "pubnotes")


class SiteHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def build_site(work, base):
    docs = work / "docs"
    docs.mkdir()
    render_group(
        ROOT / "examples/synthetic_registry.json",
        docs / "analyses",
        GroupProfile("DEMO", publication_policy=PublicationPolicy(groups=("DEMO",))),
    )
    # Reports contain diagnostic data, not site content.
    (docs / "analyses/view-report.json").unlink()
    (docs / "index.md").write_text(
        "# Synthetic integration site\n\n"
        + "\n".join(f"- [{page}](analyses/{page}.md)" for page in PAGES)
    )
    assets = ("common", "ongoing", "papers", "notes")
    config = (
        f"site_name: Synthetic integration\nsite_url: {base}\n"
        "theme:\n  name: material\n  font: false\n  features:\n    - navigation.instant\n"
        "nav:\n  - Home: index.md\n"
        + "".join(f"  - {page}: analyses/{page}.md\n" for page in PAGES)
        + "extra_css:\n"
        + "".join(f"  - analyses/assets/gal-{name}.css\n" for name in assets)
        + "extra_javascript:\n"
        + "".join(f"  - analyses/assets/gal-{name}.js\n" for name in assets)
    )
    (work / "mkdocs.yml").write_text(config)
    subprocess.run(
        [sys.executable, "-m", "zensical", "build", "--strict"], cwd=work, check=True
    )


def browse(base, driver_path):
    options = Options()
    if chrome := os.environ.get("CHROME_BINARY"):
        options.binary_location = chrome
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-background-networking")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    with webdriver.Chrome(options=options, service=Service(str(driver_path))) as driver:
        wait = WebDriverWait(driver, 15)
        driver.get(base)
        wait.until(
            lambda d: d.execute_script("return typeof document$ !== 'undefined'")
        )
        driver.execute_script("window.integrationDocument = 'preserved';")
        for page in (*PAGES, "ongoing", "papers"):
            url = base + f"analyses/{page}/"
            link = next(
                e
                for e in driver.find_elements(By.CSS_SELECTOR, "a[href]")
                if e.get_attribute("href") == url and e.is_displayed()
            )
            previous = driver.find_element(By.CSS_SELECTOR, ".md-content__inner")
            link.click()
            wait.until(EC.staleness_of(previous))
            wait.until(lambda d, url=url: d.current_url == url)
            search = wait.until(
                lambda d: next(
                    (
                        e
                        for e in d.find_elements(By.CSS_SELECTOR, "[data-gal-search]")
                        if e.is_displayed()
                    ),
                    False,
                )
            )
            assert (
                driver.execute_script("return window.integrationDocument")
                == "preserved"
            ), "Navigation reloaded the document"
            counter = (
                "[data-gal-note-count]"
                if page in {"confnotes", "pubnotes"}
                else "[data-gal-count]"
            )
            wait.until(
                lambda d, counter=counter: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith("1 of 1")
            )
            search.send_keys("no-synthetic-record-matches")
            wait.until(
                lambda d, counter=counter: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith("0 of 1")
            )
            assert "q=no-synthetic-record-matches" in driver.current_url, (
                driver.current_url
            )
            if page == "ongoing":
                Select(
                    driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
                ).select_by_value("reference")
                assert "sort=reference" in driver.current_url
            driver.refresh()
            wait.until(
                lambda d, counter=counter: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith("0 of 1")
            )
            assert (
                driver.find_element(By.CSS_SELECTOR, "[data-gal-search]").get_attribute(
                    "value"
                )
                == "no-synthetic-record-matches"
            )
            if page == "ongoing":
                assert (
                    Select(
                        driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
                    ).first_selected_option.get_attribute("value")
                    == "reference"
                )
            # A deliberate reload starts a new document; subsequent link clicks must preserve it.
            driver.execute_script("window.integrationDocument = 'preserved';")
            reset = (
                "[data-gal-note-reset]"
                if page in {"confnotes", "pubnotes"}
                else "[data-gal-reset]"
            )
            driver.find_element(By.CSS_SELECTOR, reset).click()
            assert "q=" not in driver.current_url
            assert "sort=" not in driver.current_url
            wait.until(
                lambda d, counter=counter: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith("1 of 1")
            )
            expand = (
                "[data-gal-expand-all]"
                if page == "ongoing"
                else "[data-gal-archive-expand-all]"
            )
            button = driver.find_element(By.CSS_SELECTOR, expand)
            button.click()
            wait.until(
                lambda d, button=button: button.get_attribute("aria-pressed") == "true"
            )
            button.click()
            wait.until(
                lambda d, button=button: button.get_attribute("aria-pressed") == "false"
            )
            # Confirm the package stylesheet loaded in the built theme.
            assert driver.execute_script(
                "return [...document.styleSheets].some(s => s.href && s.href.endsWith('gal-common.css') && s.cssRules.length > 0)"
            )
        errors = [
            entry for entry in driver.get_log("browser") if entry["level"] == "SEVERE"
        ]
        assert not errors, errors
        print(
            "Zensical checks passed: four pages, real instant navigation, repeat visits, search/sort URL reload, reset, expansion and assets."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="glance-zensical-") as directory:
        work = Path(directory)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(SiteHandler, directory=str(work / "site")),
        )
        try:
            base = f"http://127.0.0.1:{server.server_port}/"
            build_site(work, base)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                browse(base, args.driver)
            finally:
                server.shutdown()
                thread.join()
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
