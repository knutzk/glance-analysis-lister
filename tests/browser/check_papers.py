# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Check paper search independently of ongoing search, using synthetic records.

Run from an editable checkout with --driver /path/to/chromedriver.
"""

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import papers_page
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[2]


def run_checks(work_dir):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "tests"))
    from view_fixtures import analysis, publication, snapshot

    papers = [publication(n) for n in range(1, 5)]
    for n, paper in enumerate(papers):
        paper["publicationPhase"]["publishedOnlineDate"] = (
            f"2099-{n + 1:02}-01" if n < 3 else None
        )
        paper["gal_contactEditors"] = ["Invented Editor" if n == 0 else "Other Editor"]
        if n >= 2:
            paper["publicationPhase"]["gal_dois"] = []
        paper["gal_groups"]["subgroups"] = ["DEMO-Alpha" if n < 2 else "DEMO-Beta"]
        paper["metadata"] = {
            "gal_keywords": ["Precision" if n % 2 == 0 else "Calibration"],
            "gal_triggers": ["Trigger A" if n < 2 else "Trigger B"],
            "gal_statisticalTools": ["Tool A" if n % 2 == 0 else "Tool B"],
        }
    view = prepare_group(
        CuratedRegistry(snapshot(analysis(1), papers=tuple(papers))),
        GroupProfile("DEMO"),
    )
    markup = str(
        BeautifulSoup(papers_page(view), "html.parser").select_one(".gal-archive")
    )
    assets = ROOT / "analysis_lister/views/assets"
    css = "".join(
        f'<link rel="stylesheet" href="{(assets / name).as_uri()}">'
        for name in ("gal-common.css", "gal-ongoing.css", "gal-papers.css")
    )
    js = "".join(
        f'<script src="{(assets / name).as_uri()}"></script>'
        for name in ("gal-common.js", "gal-ongoing.js", "gal-papers.js")
    )
    path = work_dir / "fixture.html"
    path.write_text(
        f'<!doctype html><html><head><meta charset="utf-8"><style>.md-typeset details{{content-visibility:auto}}</style>{css}</head><body class="md-typeset">{markup}{js}</body></html>'
    )
    options = Options()
    for flag in (
        "--headless=new",
        "--no-first-run",
        "--disable-background-networking",
        "--window-size=1280,1000",
    ):
        options.add_argument(flag)
    service = Service(str(args.driver), log_output=str(work_dir / "chromedriver.log"))
    with webdriver.Chrome(service=service, options=options) as driver:
        wait = WebDriverWait(driver, 10)
        driver.get(path.as_uri())

        def count(n):
            wait.until(
                lambda d: (
                    d.find_element(By.CSS_SELECTOR, "[data-gal-count]").text
                    == f"{n} of 4 papers"
                )
            )

        def reset():
            driver.find_element(By.CSS_SELECTOR, "[data-gal-reset]").click()
            count(4)

        count(4)
        assert not driver.find_elements(
            By.CSS_SELECTOR, '[data-gal-filter="publication_type"]'
        )
        assert (
            len(
                [
                    r
                    for r in driver.find_elements(By.CSS_SELECTOR, "[data-gal-item]")
                    if r.is_displayed()
                ]
            )
            == 4
        )
        assert not driver.find_elements(
            By.CSS_SELECTOR, "[data-gal-pagination], [data-gal-filter='subgroups']"
        )

        def month(bound, value):
            driver.execute_script(
                "const input=document.querySelector('[data-gal-date-'+arguments[0]+']');input.value=arguments[1];input.dispatchEvent(new Event('change',{bubbles:true}))",
                bound,
                value,
            )

        month("after", "2099-02")
        count(3)
        month("before", "2099-02")
        count(1)
        assert (
            "after=2099-02" in driver.current_url
            and "before=2099-02" in driver.current_url
        )
        driver.refresh()
        count(1)
        assert (
            driver.find_element(By.CSS_SELECTOR, "[data-gal-date-after]").get_attribute(
                "value"
            )
            == "2099-02"
        )
        assert (
            driver.find_element(
                By.CSS_SELECTOR, "[data-gal-date-before]"
            ).get_attribute("value")
            == "2099-02"
        )
        month("after", "2099-03")
        count(0)
        assert driver.find_element(
            By.CSS_SELECTOR, "[data-gal-archive-expand-all]"
        ).get_attribute("disabled")
        reset()
        count(4)
        expand_all = driver.find_element(
            By.CSS_SELECTOR, "[data-gal-archive-expand-all]"
        )
        expand_all.click()
        assert expand_all.text == "Collapse all"
        assert (
            len(
                [
                    panel
                    for panel in driver.find_elements(
                        By.CSS_SELECTOR, "[data-gal-paper-details]"
                    )
                    if panel.is_displayed()
                ]
            )
            == 4
        )
        expand_all.click()
        assert expand_all.text == "Expand all"
        assert not any(
            panel.is_displayed()
            for panel in driver.find_elements(
                By.CSS_SELECTOR, "[data-gal-paper-details]"
            )
        )
        search = driver.find_element(By.CSS_SELECTOR, "[data-gal-search]")
        search.send_keys("Invented Editor")
        count(1)
        assert "q=Invented+Editor" in driver.current_url
        reset()
        published = driver.find_element(By.CSS_SELECTOR, '[data-gal-value="published"]')
        review = driver.find_element(By.CSS_SELECTOR, '[data-gal-value="under-review"]')
        published.click()
        count(2)
        assert "status=published" in driver.current_url
        review.click()
        count(4)
        published.click()
        count(2)
        reset()
        search.send_keys("no match")
        count(0)
        reset()
        assert not driver.find_elements(
            By.CSS_SELECTOR, ".gal-multiselect, [data-gal-choice]"
        )
        driver.execute_script(
            "window.GALOngoing.initialize();window.GALPapers.initialize();window.GALPapers.initialize()"
        )
        toggle = driver.find_element(By.CSS_SELECTOR, "[data-gal-paper-toggle]")
        toggle.send_keys(Keys.ENTER)
        assert toggle.get_attribute("aria-expanded") == "true"
        toggle.send_keys(Keys.SPACE)
        assert toggle.get_attribute("aria-expanded") == "false"
        toggle.click()
        panel = driver.find_element(By.ID, toggle.get_attribute("aria-controls"))
        assert panel.is_displayed()
        search.send_keys("no match")
        count(0)
        assert not panel.is_displayed()
        reset()
        assert panel.is_displayed()
        panel.find_element(By.CSS_SELECTOR, "[data-gal-paper-collapse]").click()
        assert not panel.is_displayed()
        toggle.click()
        toggle.click()
        assert not panel.is_displayed()

        original = driver.execute_script(
            "return document.querySelector('[data-gal-archive]').outerHTML"
        )
        driver.execute_script(
            "document.querySelector('[data-gal-archive]').outerHTML=arguments[0]",
            original,
        )
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-gal-controls]"
            ).is_displayed()
        )
        driver.find_element(By.CSS_SELECTOR, "[data-gal-search]").send_keys("Precision")
        count(2)
        reset()
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
        driver.refresh()
        assert (
            len(
                [
                    r
                    for r in driver.find_elements(By.CSS_SELECTOR, "[data-gal-item]")
                    if r.is_displayed()
                ]
            )
            == 4
        )
        assert not driver.find_element(
            By.CSS_SELECTOR, "[data-gal-controls]"
        ).is_displayed()
        print(
            "Paper browser checks passed: independent initialization, filters, search, unpaginated rows, row disclosure, document replacement and no-JavaScript fallback."
        )


def main():
    with TemporaryDirectory(prefix="gal-papers-browser-") as directory:
        run_checks(Path(directory))


if __name__ == "__main__":
    main()
