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
from urllib.parse import parse_qs, urlsplit

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


def check_filter_subsets(driver, wait, page):
    """Exercise nonempty intersections and note supersession in the public demo."""
    notes = page in {"confnotes", "pubnotes"}
    counter = "[data-gal-note-count]" if notes else "[data-gal-count]"
    reset = "[data-gal-note-reset]" if notes else "[data-gal-reset]"
    search = driver.find_element(By.CSS_SELECTOR, "[data-gal-search]")

    def count(expected):
        wait.until(
            lambda d: d.find_element(By.CSS_SELECTOR, counter).text.startswith(
                f"{expected} of 4"
            )
        )

    def click(selector):
        driver.find_element(By.CSS_SELECTOR, selector).click()

    def month(bound, value):
        driver.execute_script(
            "const input = document.querySelector(arguments[0]);"
            "input.value = arguments[1];"
            "input.dispatchEvent(new Event('input', {bubbles: true}));"
            "input.dispatchEvent(new Event('change', {bubbles: true}));",
            f"[data-gal-date-{bound}]",
            value,
        )

    search.send_keys("Tracking")
    count(2)
    if page == "ongoing":
        click(reset)
        click('[data-gal-value="DEMO-Tracking"]')
        count(2)
        click('[data-gal-value="DEMO-Calorimetry"]')
        count(3)  # OR across subgroups; the shared analysis is counted once.
        search.send_keys("Calibration")
        count(1)  # Search must also match.
    elif page == "papers":
        click('[data-gal-value="published"]')
        count(1)
        click(reset)
        click('[data-gal-value="under-review"]')
        count(2)
        search.send_keys("Tracking")
        count(1)
        click(reset)
        month("before", "2099-01")
        count(1)  # The older published paper; undated submissions are excluded.
    else:
        click(reset)
        click('[data-gal-note-supersession="superseded"]')
        count(4)
        click('[data-gal-note-supersession="non-superseded"]')
        count(1)
        search.send_keys("Simulation")
        count(1)
        click(reset)
        month("after", "2099-06")
        month("before", "2099-08")
        count(1)
    click(reset)
    count(3 if notes else 4)


def check_saved_links(driver, wait, base, page_prefix):
    # Literal bookmarks protect the public URL forms independently of whatever
    # query strings the current controls generate. Keep these forms readable.
    bookmarks = (
        (
            "ongoing",
            "q=Tracking&subgroup=DEMO-Tracking&subgroup=DEMO-Calorimetry&sort=reference",
            "analysis-demo-ana-demo-2099-02",
            2,
        ),
        (
            "papers",
            "q=Tracking&status=published&status=under-review&after=2098-01&before=2098-12",
            "publication-papers-demo-demo-2099-02",
            1,
        ),
        (
            "confnotes",
            "q=Simulation&supersession=all&after=2098-01&before=2098-12",
            "confnote-demo-conf-demo-2099-03",
            1,
        ),
        (
            "pubnotes",
            "q=Simulation&supersession=superseded&after=2098-01&before=2098-12",
            "pubnote-demo-pub-demo-2099-03",
            1,
        ),
    )
    for page, query, fragment, expected in bookmarks:
        notes = page in {"confnotes", "pubnotes"}
        counter = "[data-gal-note-count]" if notes else "[data-gal-count]"
        reset = "[data-gal-note-reset]" if notes else "[data-gal-reset]"
        driver.get(base + f"{page_prefix}{page}/?{query}&source=bookmark#{fragment}")
        for reload in (False, True):
            if reload:
                driver.refresh()
            wait.until(
                lambda d, counter=counter, expected=expected: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith(f"{expected} of 4")
            )
            assert driver.find_element(By.ID, fragment).is_displayed()
            actual = urlsplit(driver.current_url)
            assert actual.fragment == fragment
            params = parse_qs(actual.query)
            assert params["source"] == ["bookmark"]
            for key, values in parse_qs(query).items():
                assert sorted(params[key]) == sorted(values), (page, key, params)
        driver.find_element(By.CSS_SELECTOR, reset).click()
        wait.until(
            lambda d, counter=counter, notes=notes: d.find_element(
                By.CSS_SELECTOR, counter
            ).text.startswith(f"{3 if notes else 4} of 4")
        )
        actual = urlsplit(driver.current_url)
        assert parse_qs(actual.query) == {"source": ["bookmark"]}
        assert actual.fragment == fragment


def browse(base, driver_path, *, page_prefix="analyses/", start_page=""):
    options = Options()
    if chrome := os.environ.get("CHROME_BINARY"):
        options.binary_location = chrome
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-background-networking")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    with webdriver.Chrome(options=options, service=Service(str(driver_path))) as driver:
        wait = WebDriverWait(driver, 15)
        driver.get(base + start_page)
        wait.until(
            lambda d: d.execute_script("return typeof document$ !== 'undefined'")
        )
        driver.execute_script("window.integrationDocument = 'preserved';")
        for page in (*PAGES, "ongoing", "papers"):
            url = base + f"{page_prefix}{page}/"
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
            default_count = 3 if page in {"confnotes", "pubnotes"} else 4
            wait.until(
                lambda d, counter=counter, default_count=default_count: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith(f"{default_count} of 4")
            )
            check_filter_subsets(driver, wait, page)
            search.send_keys("no-synthetic-record-matches")
            wait.until(
                lambda d, counter=counter: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith("0 of 4")
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
                ).text.startswith("0 of 4")
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
                lambda d, counter=counter, default_count=default_count: d.find_element(
                    By.CSS_SELECTOR, counter
                ).text.startswith(f"{default_count} of 4")
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
        check_saved_links(driver, wait, base, page_prefix)
        errors = [
            entry for entry in driver.get_log("browser") if entry["level"] == "SEVERE"
        ]
        assert not errors, errors
        print(
            "Zensical checks passed: four pages, nonempty filter subsets, supersession, real instant navigation, repeat visits, search/sort URL reload, reset, expansion and assets."
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
