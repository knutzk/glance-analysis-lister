# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise CONF/PUB-note search, dates, supersession and expansion with synthetic records."""

import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from diagnostics import chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from timing import timed

from grove.registry import CuratedRegistry
from grove.views.markdown.pages import confnotes_page, pubnotes_page
from grove.views.prepare import prepare_group
from grove.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[2]


def run_checks(work_dir):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument(
        "--resource", choices=("confnotes", "pubnotes"), default="confnotes"
    )
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "tests"))
    from view_fixtures import analysis, publication, snapshot

    notes = [
        publication(n, resource=args.resource, status="Phase 1 Finished")
        for n in range(1, 5)
    ]
    for n, note in enumerate(notes):
        note["phase1"]["releaseDate"] = f"2099-{n + 1:02}-01" if n < 3 else None
        note["grove_groups"]["leadingSubgroup"] = (
            "DEMO-Alpha" if n == 0 else "DEMO-Beta" if n < 3 else "OTHER-Outside"
        )
        note["grove_groups"]["subgroups"] = ["DEMO-Alpha"] if n == 1 else []
        note["phase1"]["draftCdsUrl"] = f"https://cds.cern.ch/record/20990000000{n}"
    notes[0]["grove_contactEditors"] = ["Invented Editor"]
    notes[2]["supersededBy"] = [{"type": "Paper", "referenceCode": "DEMO-2099-77"}]
    view = prepare_group(
        CuratedRegistry(snapshot(analysis(1), **{args.resource: tuple(notes)})),
        GroupProfile("DEMO"),
    )
    markup = str(
        BeautifulSoup(
            (confnotes_page if args.resource == "confnotes" else pubnotes_page)(view),
            "html.parser",
        ).select_one("[data-grove-notes]")
    )
    assets = ROOT / "grove/views/assets"
    css = "".join(
        f'<link rel="stylesheet" href="{(assets / name).as_uri()}">'
        for name in (
            "grove-common.css",
            "grove-ongoing.css",
            "grove-papers.css",
            "grove-notes.css",
        )
    )
    js = "".join(
        f'<script src="{(assets / name).as_uri()}"></script>'
        for name in (
            "grove-common.js",
            "grove-ongoing.js",
            "grove-papers.js",
            "grove-notes.js",
        )
    )
    output = work_dir / "fixture.html"
    output.write_text(
        f'<!doctype html><html><head><meta charset="utf-8">{css}</head><body>{markup}{js}</body></html>'
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
    with chrome(
        options=options, driver_path=args.driver, label=args.resource
    ) as driver:
        wait = WebDriverWait(driver, 10, poll_frequency=0.1)
        driver.get(output.as_uri())
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-grove-note-controls]"
            ).is_displayed()
        )

        def visible():
            return [
                r
                for r in driver.find_elements(By.CSS_SELECTOR, "[data-grove-note]")
                if r.is_displayed()
            ]

        def count(n):
            wait.until(
                lambda d: (
                    len(visible()) == n
                    and d.find_element(By.CSS_SELECTOR, "[data-grove-note-count]").text
                    == f"{n} of 4 notes"
                )
            )

        def search_for(value):
            search = driver.find_element(By.CSS_SELECTOR, "[data-grove-search]")
            search.clear()
            search.send_keys(value)

        count(3)
        search_for("209900000000")
        count(1)
        assert "q=209900000000" in driver.current_url
        search_for("Invented Editor")
        count(1)
        driver.find_element(By.CSS_SELECTOR, "[data-grove-note-reset]").click()
        count(3)

        def month(bound, value):
            driver.execute_script(
                "const input=document.querySelector('[data-grove-date-'+arguments[0]+']');input.value=arguments[1];input.dispatchEvent(new Event('change',{bubbles:true}))",
                bound,
                value,
            )

        month("after", "2099-02")
        count(2)
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
        driver.find_element(By.CSS_SELECTOR, "[data-grove-note-reset]").click()
        count(3)
        expand_all = driver.find_element(
            By.CSS_SELECTOR, "[data-grove-archive-expand-all]"
        )
        expand_all.click()
        assert expand_all.text == "Collapse all"
        assert (
            len(
                [
                    panel
                    for panel in driver.find_elements(
                        By.CSS_SELECTOR, "[data-grove-note-details]"
                    )
                    if panel.is_displayed()
                ]
            )
            == 3
        )
        expand_all.click()
        assert expand_all.text == "Expand all"
        assert not any(
            panel.is_displayed()
            for panel in driver.find_elements(
                By.CSS_SELECTOR, "[data-grove-note-details]"
            )
        )
        assert not driver.find_elements(
            By.CSS_SELECTOR,
            "[data-grove-filter='subgroups'], [data-grove-pagination], [data-grove-disclosure]",
        )
        assert not driver.find_elements(
            By.CSS_SELECTOR, '[data-grove-value="OTHER-Outside"]'
        )
        assert all(
            len(row.find_elements(By.CSS_SELECTOR, "td, th")) == 3 for row in visible()
        )
        assert driver.execute_script(
            "return Array.from(document.querySelectorAll('.grove-notes tbody tr[data-grove-note] > *')).every(e=>getComputedStyle(e).whiteSpace==='nowrap')"
        )
        driver.execute_script(
            "window.GROVEOngoing.initialize();window.GROVEPapers.initialize();window.GROVENotes.initialize();window.GROVENotes.initialize()"
        )
        current = driver.find_element(
            By.CSS_SELECTOR, '[data-grove-note-supersession="non-superseded"]'
        )
        superseded = driver.find_element(
            By.CSS_SELECTOR, '[data-grove-note-supersession="superseded"]'
        )
        superseded.click()
        count(4)
        current.click()
        count(1)
        assert "supersession=superseded" in driver.current_url
        driver.refresh()
        count(1)
        driver.find_element(By.CSS_SELECTOR, "[data-grove-note-reset]").click()
        count(3)
        row = next(
            row
            for row in visible()
            if "OTHER-Outside" in row.get_attribute("data-grove-search-text")
        )
        toggle = row.find_element(By.CSS_SELECTOR, "[data-grove-note-toggle]")
        panel_id = toggle.get_attribute("aria-controls")
        toggle.send_keys(Keys.ENTER)
        panel = driver.find_element(By.ID, panel_id)
        assert panel.is_displayed()
        panel.find_element(By.CSS_SELECTOR, "dd").click()
        assert panel.is_displayed()
        row.find_element(By.CSS_SELECTOR, "[data-grove-note-toggle]").click()
        assert not panel.is_displayed()
        row.find_element(By.CSS_SELECTOR, "[data-grove-note-toggle]").send_keys(
            Keys.ENTER
        )
        assert panel.is_displayed()
        assert driver.execute_script(
            "return getComputedStyle(arguments[0]).backgroundColor===getComputedStyle(document.querySelector('.grove-note-detail-row > td')).backgroundColor",
            panel,
        )

        search_for("DEMO-Alpha")
        count(2)
        assert not panel.is_displayed()
        driver.find_element(By.CSS_SELECTOR, "[data-grove-note-reset]").click()
        count(3)
        assert panel.is_displayed()
        panel.find_element(By.CSS_SELECTOR, "[data-grove-note-collapse]").send_keys(
            Keys.SPACE
        )
        assert not panel.is_displayed()
        assert driver.switch_to.active_element == toggle
        link = row.find_element(By.CSS_SELECTOR, "a")
        driver.execute_script(
            "arguments[0].addEventListener('click',e=>e.preventDefault(),{once:true});arguments[0].click()",
            link,
        )
        assert not panel.is_displayed()

        search_for("DEMO-Alpha")
        count(2)
        assert "q=DEMO-Alpha" in driver.current_url
        assert (
            sum("grove-note--stripe" in row.get_attribute("class") for row in visible())
            == 1
        )
        search_for("DEMO-Beta")
        count(1)
        driver.refresh()
        count(1)
        driver.find_element(By.CSS_SELECTOR, "[data-grove-note-reset]").click()
        count(3)
        row = next(
            row
            for row in visible()
            if "OTHER-Outside" in row.get_attribute("data-grove-search-text")
        )
        before = row.value_of_css_property("background-color")
        ActionChains(driver).move_to_element(row).perform()
        wait.until(lambda _: row.value_of_css_property("background-color") != before)
        driver.set_window_size(390, 1000)
        assert driver.execute_script(
            "return document.documentElement.scrollWidth<=window.innerWidth"
        )
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
        driver.refresh()
        count(4)
        assert not driver.find_element(
            By.CSS_SELECTOR, "[data-grove-note-controls]"
        ).is_displayed()
        assert all(
            p.is_displayed()
            for p in driver.find_elements(By.CSS_SELECTOR, "[data-grove-note-details]")
        )
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": False})
        driver.get(output.as_uri())
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-grove-note-controls]"
            ).is_displayed()
        )
        driver.execute_script(
            "const root=document.querySelector('[data-grove-notes]');const copy=root.cloneNode(true);copy.querySelector('[data-grove-note-controls]').remove();root.replaceWith(copy)"
        )
        toggle = driver.find_element(By.CSS_SELECTOR, "[data-grove-note-toggle]")
        toggle.send_keys(Keys.ENTER)
        assert driver.find_element(
            By.ID, toggle.get_attribute("aria-controls")
        ).is_displayed()
        print(
            f"{args.resource} browser checks passed: three single-line columns and expandable details, free-text subgroup/people/CDS search, date bounds, URL reload, visible-row striping, hover, keyboard, mobile scrolling and static fallback."
        )


def main():
    with TemporaryDirectory(prefix="grove-notes-browser-") as directory:
        run_checks(Path(directory))


if __name__ == "__main__":
    with timed("check_notes"):
        main()
