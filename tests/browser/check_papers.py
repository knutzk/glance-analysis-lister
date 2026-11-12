# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Check paper search independently of ongoing search, using synthetic records.

Run from an editable checkout with --driver /path/to/chromedriver.
"""

import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from diagnostics import chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from timing import timed

from grove.registry import CuratedRegistry
from grove.views.markdown.pages import papers_page
from grove.views.prepare import prepare_group
from grove.views.profiles import GroupProfile

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
        paper["grove_contactEditors"] = [
            "Invented Editor" if n == 0 else "Other Editor"
        ]
        if n >= 2:
            paper["publicationPhase"]["grove_dois"] = []
        paper["grove_groups"]["subgroups"] = ["DEMO-Alpha" if n < 2 else "DEMO-Beta"]
        paper["metadata"] = {
            "grove_keywords": ["Precision" if n % 2 == 0 else "Calibration"],
            "grove_triggers": ["Trigger A" if n < 2 else "Trigger B"],
            "grove_statisticalTools": ["Tool A" if n % 2 == 0 else "Tool B"],
        }
    papers[0]["publicationPhase"]["finalTitleTex"] = r"Invented $X \to Y$ measurement"
    papers[0]["publicationPhase"]["arXivUrls"] = [
        {"url": "https://arxiv.org/abs/9901.12345"}
    ]
    papers[1]["publicationPhase"]["arXivUrls"] = [
        {"url": "https://example.test/arxiv/2099.00001"}
    ]
    papers[1]["publicationPhase"]["grove_dois"] = [
        {"doi": "10.9999/synthetic", "citation": "Invented Journal 123 (2099) 456"},
        {
            "doi": "10.9999/synthetic-erratum",
            "citation": "Erratum: Invented Journal 124 (2099) 789",
        },
    ]
    view = prepare_group(
        CuratedRegistry(snapshot(analysis(1), papers=tuple(papers))),
        GroupProfile("DEMO"),
    )
    markup = str(
        BeautifulSoup(papers_page(view), "html.parser").select_one(".grove-archive")
    )
    assets = ROOT / "grove/views/assets"
    css = "".join(
        f'<link rel="stylesheet" href="{(assets / name).as_uri()}">'
        for name in ("grove-common.css", "grove-ongoing.css", "grove-papers.css")
    )
    js = "".join(
        f'<script src="{(assets / name).as_uri()}"></script>'
        for name in ("grove-common.js", "grove-ongoing.js", "grove-papers.js")
    )
    path = work_dir / "fixture.html"
    path.write_text(
        f'<!doctype html><html><head><meta charset="utf-8"><style>.md-typeset details{{content-visibility:auto}}</style>{css}</head><body class="md-typeset">{markup}{js}</body></html>'
    )
    options = Options()
    if binary := os.environ.get("CHROME_BINARY"):
        options.binary_location = binary
    for flag in (
        "--headless=new",
        "--no-first-run",
        "--disable-background-networking",
        "--window-size=1280,1000",
    ):
        options.add_argument(flag)
    with chrome(options=options, driver_path=args.driver) as driver:
        wait = WebDriverWait(driver, 10, poll_frequency=0.1)
        driver.get(path.as_uri())

        def count(n):
            wait.until(
                lambda d: (
                    d.find_element(By.CSS_SELECTOR, "[data-grove-count]").text
                    == f"{n} of 4 papers"
                )
            )

        def reset():
            driver.find_element(By.CSS_SELECTOR, "[data-grove-reset]").click()
            count(4)

        count(4)

        def check_link_layout():
            for width in (640, 800, 1000):
                driver.execute_script(
                    "document.querySelector('.grove-archive').style.maxWidth = arguments[0] + 'px'",
                    width,
                )
                dimensions = driver.execute_script("""
                    const scroll = document.querySelector('.grove-table-scroll');
                    const links = [...document.querySelectorAll('.grove-publication-records a')]
                        .filter(a => a.href.includes('example.test/arxiv') || a.href.includes('10.9999/synthetic'));
                    const erratum = links.find(a => a.textContent.startsWith('Erratum:'));
                    const arxiv = links.find(a => a.textContent === 'arXiv');
                    return {
                        width: scroll.clientWidth, content: scroll.scrollWidth,
                        height: scroll.clientHeight, contentHeight: scroll.scrollHeight,
                        wrapped: erratum.getBoundingClientRect().top > arxiv.getBoundingClientRect().top,
                        contained: links.every(a => {
                            const cell = a.closest('td').getBoundingClientRect();
                            const rect = a.getBoundingClientRect();
                            return rect.left >= cell.left && rect.right <= cell.right
                                && a.scrollWidth <= a.clientWidth + 1;
                        })
                    };
                """)
                assert dimensions["content"] <= dimensions["width"] + 1, dimensions
                assert dimensions["contentHeight"] <= dimensions["height"] + 1, (
                    dimensions
                )
                assert dimensions["wrapped"] and dimensions["contained"], dimensions
            driver.execute_script(
                "document.querySelector('.grove-archive').style.removeProperty('max-width')"
            )

        check_link_layout()
        assert not driver.find_elements(
            By.CSS_SELECTOR, '[data-grove-filter="publication_type"]'
        )
        assert (
            len(
                [
                    r
                    for r in driver.find_elements(By.CSS_SELECTOR, "[data-grove-item]")
                    if r.is_displayed()
                ]
            )
            == 4
        )
        assert not driver.find_elements(
            By.CSS_SELECTOR, "[data-grove-pagination], [data-grove-filter='subgroups']"
        )

        def month(bound, value):
            driver.execute_script(
                "const input=document.querySelector('[data-grove-date-'+arguments[0]+']');input.value=arguments[1];input.dispatchEvent(new Event('change',{bubbles:true}))",
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
            driver.find_element(
                By.CSS_SELECTOR, "[data-grove-date-after]"
            ).get_attribute("value")
            == "2099-02"
        )
        assert (
            driver.find_element(
                By.CSS_SELECTOR, "[data-grove-date-before]"
            ).get_attribute("value")
            == "2099-02"
        )
        month("after", "2099-03")
        count(0)
        assert driver.find_element(
            By.CSS_SELECTOR, "[data-grove-archive-expand-all]"
        ).get_attribute("disabled")
        reset()
        count(4)
        expand_all = driver.find_element(
            By.CSS_SELECTOR, "[data-grove-archive-expand-all]"
        )
        expand_all.click()
        assert expand_all.text == "Collapse all"
        citations = driver.find_elements(By.CSS_SELECTOR, ".grove-paper-citation")
        assert len(citations) == 4
        assert all(block.is_displayed() for block in citations)
        complete = next(
            block for block in citations if "arXiv:9901.12345" in block.text
        )
        assert complete.text.splitlines() == [
            "ATLAS Collaboration",
            r"Invented $X \to Y$ measurement",
            "Synthetic citation, arXiv:9901.12345",
            "DOI: 10.9999/synthetic",
        ]
        selected = driver.execute_script(
            "const range = document.createRange(); range.selectNodeContents(arguments[0]); "
            "const selection = window.getSelection(); selection.removeAllRanges(); "
            "selection.addRange(range); return selection.toString();",
            complete,
        )
        assert selected == complete.text
        check_link_layout()
        assert (
            len(
                [
                    panel
                    for panel in driver.find_elements(
                        By.CSS_SELECTOR, "[data-grove-paper-details]"
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
                By.CSS_SELECTOR, "[data-grove-paper-details]"
            )
        )
        search = driver.find_element(By.CSS_SELECTOR, "[data-grove-search]")
        search.send_keys("Invented Editor")
        count(1)
        assert "q=Invented+Editor" in driver.current_url
        reset()
        published = driver.find_element(
            By.CSS_SELECTOR, '[data-grove-value="published"]'
        )
        review = driver.find_element(
            By.CSS_SELECTOR, '[data-grove-value="under-review"]'
        )
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
            By.CSS_SELECTOR, ".grove-multiselect, [data-grove-choice]"
        )
        driver.execute_script(
            "window.GROVEOngoing.initialize();window.GROVEPapers.initialize();window.GROVEPapers.initialize()"
        )
        toggle = driver.find_element(By.CSS_SELECTOR, "[data-grove-paper-toggle]")
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
        panel.find_element(By.CSS_SELECTOR, "[data-grove-paper-collapse]").click()
        assert not panel.is_displayed()
        toggle.click()
        toggle.click()
        assert not panel.is_displayed()

        original = driver.execute_script(
            "return document.querySelector('[data-grove-archive]').outerHTML"
        )
        driver.execute_script(
            "document.querySelector('[data-grove-archive]').outerHTML=arguments[0]",
            original,
        )
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-grove-controls]"
            ).is_displayed()
        )
        driver.find_element(By.CSS_SELECTOR, "[data-grove-search]").send_keys(
            "Precision"
        )
        count(2)
        reset()
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
        driver.refresh()
        assert (
            len(
                [
                    r
                    for r in driver.find_elements(By.CSS_SELECTOR, "[data-grove-item]")
                    if r.is_displayed()
                ]
            )
            == 4
        )
        assert not driver.find_element(
            By.CSS_SELECTOR, "[data-grove-controls]"
        ).is_displayed()
        assert all(
            block.is_displayed()
            for block in driver.find_elements(By.CSS_SELECTOR, ".grove-paper-citation")
        )
        check_link_layout()
        print(
            "Paper browser checks passed: copy-ready citations, independent initialization, filters, search, unpaginated rows, row disclosure, document replacement and no-JavaScript fallback."
        )


def main():
    with TemporaryDirectory(prefix="grove-papers-browser-") as directory:
        run_checks(Path(directory))


if __name__ == "__main__":
    with timed("check_papers"):
        main()
