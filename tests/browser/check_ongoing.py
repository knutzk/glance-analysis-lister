# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise card filtering in local Chrome using synthetic records only.

Run from an editable development checkout:
    python tests/browser/check_ongoing.py --driver /path/to/chromedriver
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
from selenium.webdriver.support.ui import Select, WebDriverWait

from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.markdown.pages import ongoing_page
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile

ROOT = Path(__file__).resolve().parents[2]


def choose_filter(driver, category, value):
    container = driver.find_element(By.CSS_SELECTOR, f'[data-gal-filter="{category}"]')
    if category == "subgroups":
        for button in container.find_elements(By.CSS_SELECTOR, "button"):
            expected = button.get_attribute("data-gal-value") == value
            if (button.get_attribute("aria-pressed") == "true") != expected:
                button.click()
        return


def run_checks(work_dir):
    sys.path.insert(0, str(ROOT / "tests"))
    from view_fixtures import analysis, snapshot

    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument(
        "--driver",
        type=Path,
        required=True,
        help="Installed ChromeDriver path; no driver is downloaded.",
    )
    args = arguments.parse_args()
    root = ROOT
    first, second, third, fourth = (
        analysis(1),
        analysis(2, group="OTHER", additional=("DEMO",)),
        analysis(3),
        analysis(4),
    )
    for record, names in (
        (first, ["DEMO-Alpha, with comma"]),
        (second, ["DEMO-Beta"]),
        (third, ["DEMO-Alpha, with comma", "DEMO-Beta"]),
        (fourth, []),
    ):
        record["gal_groups"]["leadingSubgroup"] = names[0] if names else None
        record["gal_groups"]["subgroups"] = names
    for record in (first, second, third, fourth):
        record["metadata"]["gal_keywords"] = [
            "Signal" if record in (first, fourth) else "Background"
        ]
    first["metadata"]["gal_triggers"] = ["Invented trigger"]
    first["shortTitle"] = "Synthetic first analysis"
    second["shortTitle"] = "Synthetic second analysis"
    second["phase0"]["gal_editorialBoard"] = ["Example Reviewer"]
    third["shortTitle"] = "Synthetic third analysis"
    third["phase0"]["pgcOrSgcSignOffDate"] = "2099-01-02"
    fourth["shortTitle"] = "Synthetic analysis without subgroup"
    view = prepare_group(
        CuratedRegistry(snapshot(first, second, third, fourth)), GroupProfile("DEMO")
    )
    markup = str(
        BeautifulSoup(ongoing_page(view), "html.parser").select_one(".gal-ongoing")
    )
    common_css = (root / "analysis_lister/views/assets/gal-common.css").as_uri()
    common_js = (root / "analysis_lister/views/assets/gal-common.js").as_uri()
    css = (root / "analysis_lister/views/assets/gal-ongoing.css").as_uri()
    js = (root / "analysis_lister/views/assets/gal-ongoing.js").as_uri()
    archive_js = (root / "analysis_lister/views/assets/gal-papers.js").as_uri()
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>.md-typeset details {{ content-visibility: auto; }} .md-typeset ol:not([hidden]), .md-typeset ul:not([hidden]) {{ display: flow-root; }}</style><link rel="stylesheet" href="{common_css}"><link rel="stylesheet" href="{css}"><style>body{{font:16px system-ui;max-width:1000px;margin:auto;padding:24px;background:#fafbfc;color:#253041}}p{{line-height:1.5}}</style></head><body><main class="md-typeset">{markup}</main><script>window.document$={{subscribe(fn){{window.documentSubscriber=fn;}}}};</script><script src="{common_js}"></script><script src="{js}"></script><script src="{archive_js}"></script></body></html>'''
    output = work_dir / "fixture.html"
    output.write_text(html)
    options = Options()
    for value in (
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-extensions",
        "--window-size=1280,1600",
    ):
        options.add_argument(value)
    service = Service(str(args.driver), log_output=str(work_dir / "chromedriver.log"))
    with webdriver.Chrome(options=options, service=service) as driver:
        wait = WebDriverWait(driver, 10)
        driver.get(output.as_uri())

        def count(value):
            wait.until(
                lambda d: (
                    d.find_element(By.CSS_SELECTOR, "[data-gal-count]").text
                    == f"{value} of 4 analyses"
                )
            )

        def button(value):
            return driver.find_element(By.CSS_SELECTOR, f'[data-gal-value="{value}"]')

        def reset():
            driver.find_element(By.CSS_SELECTOR, "[data-gal-reset]").click()
            count(4)

        driver.get(
            output.as_uri() + "?q=Signal&sort=reference&unrelated=keep#synthetic-anchor"
        )
        count(2)
        assert (
            driver.find_element(By.CSS_SELECTOR, "[data-gal-search]").get_attribute(
                "value"
            )
            == "Signal"
        )
        assert (
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
            ).first_selected_option.get_attribute("value")
            == "reference"
        )
        search = driver.find_element(By.CSS_SELECTOR, "[data-gal-search]")
        search.clear()
        search.send_keys("Invented trigger")
        count(1)
        assert "q=Invented+trigger" in driver.current_url
        assert driver.current_url.endswith("#synthetic-anchor")
        driver.refresh()
        count(1)
        assert "sort=reference" in driver.current_url
        reset()
        assert "q=" not in driver.current_url and "sort=" not in driver.current_url
        assert "unrelated=keep" in driver.current_url
        assert driver.current_url.endswith("#synthetic-anchor")
        driver.execute_script(
            "history.pushState(null, '', '?q=Signal&sort=stage-asc'); window.dispatchEvent(new PopStateEvent('popstate'))"
        )
        count(2)
        assert (
            driver.find_element(By.CSS_SELECTOR, "[data-gal-search]").get_attribute(
                "value"
            )
            == "Signal"
        )
        assert (
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
            ).first_selected_option.get_attribute("value")
            == "stage-asc"
        )
        # Exercise actual back/forward traversal, not just a dispatched popstate.
        driver.execute_script(
            "history.pushState(null, '', '?q=Background&sort=reference'); window.dispatchEvent(new PopStateEvent('popstate'))"
        )
        count(2)
        driver.back()
        wait.until(
            lambda d: (
                d.find_element(By.CSS_SELECTOR, "[data-gal-search]").get_attribute(
                    "value"
                )
                == "Signal"
            )
        )
        count(2)
        assert (
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
            ).first_selected_option.get_attribute("value")
            == "stage-asc"
        )
        driver.forward()
        wait.until(
            lambda d: (
                d.find_element(By.CSS_SELECTOR, "[data-gal-search]").get_attribute(
                    "value"
                )
                == "Background"
            )
        )
        count(2)
        assert (
            Select(
                driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]")
            ).first_selected_option.get_attribute("value")
            == "reference"
        )
        driver.get(output.as_uri() + "?sort=invalid")
        count(4)
        assert "sort=" not in driver.current_url

        driver.get(output.as_uri() + "?subgroup=DEMO-Alpha%2C+with+comma")
        count(2)
        assert button("DEMO-Alpha, with comma").get_attribute("aria-pressed") == "true"
        driver.refresh()
        count(2)
        button("DEMO-Beta").click()
        count(3)
        assert driver.current_url.count("subgroup=") == 2
        reset()
        assert "subgroup=" not in driver.current_url
        driver.execute_script(
            "history.pushState(null, '', '?subgroup=DEMO-Beta'); window.dispatchEvent(new PopStateEvent('popstate'))"
        )
        count(2)
        reset()
        count(4)
        card = driver.find_element(By.CSS_SELECTOR, ".gal-card")
        toggle = card.find_element(By.CSS_SELECTOR, "[data-gal-card-toggle]")
        assert toggle.get_attribute("aria-expanded") == "false"
        card.find_element(By.CSS_SELECTOR, "h2").click()
        assert toggle.get_attribute("aria-expanded") == "true"
        collapse = card.find_element(By.CSS_SELECTOR, "[data-gal-card-collapse]")
        card.find_element(By.CSS_SELECTOR, ".gal-progress").click()
        assert toggle.get_attribute("aria-expanded") == "true"
        collapse.click()
        assert toggle.get_attribute("aria-expanded") == "false"
        toggle.send_keys(Keys.ENTER)
        assert toggle.get_attribute("aria-expanded") == "true"
        collapse.send_keys(Keys.SPACE)
        assert toggle.get_attribute("aria-expanded") == "false"
        assert not card.find_elements(By.CSS_SELECTOR, "summary")
        assert (
            card.find_element(By.CSS_SELECTOR, ".gal-card__header").rect["y"]
            < card.find_element(By.CSS_SELECTOR, ".gal-progress").rect["y"]
        )
        assert driver.find_element(
            By.CSS_SELECTOR, "[data-gal-controls]"
        ).is_displayed()

        expand_all = driver.find_element(By.CSS_SELECTOR, "[data-gal-expand-all]")
        expand_all.click()
        assert expand_all.text == "Collapse all"
        assert all(
            p.is_displayed()
            for p in driver.find_elements(By.CSS_SELECTOR, ".gal-card__details")
        )
        expand_all.click()
        assert expand_all.text == "Expand all"
        assert not any(
            p.is_displayed()
            for p in driver.find_elements(By.CSS_SELECTOR, ".gal-card__details")
        )
        target = driver.find_elements(By.CSS_SELECTOR, ".gal-card")[-1]
        target_id = target.get_attribute("id")
        permalink = target.find_element(By.CSS_SELECTOR, ".gal-card__permalink")
        assert permalink.get_attribute("href").endswith("#" + target_id)
        permalink.click()
        assert target.find_element(By.CSS_SELECTOR, ".gal-card__details").is_displayed()
        driver.refresh()
        count(4)
        assert (
            driver.find_element(By.ID, target_id)
            .find_element(By.CSS_SELECTOR, ".gal-card__details")
            .is_displayed()
        )
        # A direct card link reveals its target even if a subgroup URL hides it.
        driver.get(
            output.as_uri()
            + "?subgroup=DEMO-Alpha%2C+with+comma#analysis-demo-ana-demo-2099-04"
        )
        count(4)
        assert (
            driver.find_element(By.ID, "analysis-demo-ana-demo-2099-04")
            .find_element(By.CSS_SELECTOR, ".gal-card__details")
            .is_displayed()
        )
        driver.get(output.as_uri())
        count(4)

        def choose(category, value):
            choose_filter(driver, category, value)

        button("DEMO-Alpha, with comma").click()
        count(2)
        button("DEMO-Beta").click()
        count(3)
        reset()
        choose("subgroups", "DEMO-Alpha, with comma")
        count(2)
        assert not driver.find_elements(
            By.CSS_SELECTOR,
            '[data-gal-filter="keywords"], [data-gal-filter="triggers"]',
        )
        search = driver.find_element(By.CSS_SELECTOR, "[data-gal-search]")
        search.send_keys("Signal")
        count(1)
        search.clear()
        search.send_keys("Invented trigger")
        count(1)
        search.clear()
        count(2)
        sorter = Select(driver.find_element(By.CSS_SELECTOR, "[data-gal-sort]"))
        sorter.select_by_value("stage-desc")
        count(2)
        assert (
            driver.execute_script(
                "return JSON.parse(document.querySelector('.gal-card').dataset.galMetadata).reference"
            )
            == "ANA-DEMO-2099-03"
        )
        sorter.select_by_value("stage-asc")
        assert (
            driver.execute_script(
                "return JSON.parse(document.querySelector('.gal-card').dataset.galMetadata).reference"
            )
            == "ANA-DEMO-2099-01"
        )
        search = driver.find_element(By.CSS_SELECTOR, "[data-gal-search]")
        search.send_keys("no-match")
        count(0)
        assert driver.find_element(By.CSS_SELECTOR, "[data-gal-empty]").is_displayed()
        reset()
        assert not driver.find_elements(
            By.CSS_SELECTOR,
            '[data-gal-filter="stage"], [data-gal-filter="participation"], [data-gal-filter="statistical_tools"]',
        )
        driver.execute_script(
            "window.documentSubscriber();window.documentSubscriber();"
        )
        choose("subgroups", "DEMO-Beta")
        count(2)
        reset()
        original = driver.execute_script(
            'return document.querySelector("[data-gal-collection]").outerHTML'
        )
        driver.execute_script(
            'document.querySelector("[data-gal-collection]").outerHTML=arguments[0]',
            original,
        )
        wait.until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-gal-controls]"
            ).is_displayed()
        )
        button("DEMO-Alpha, with comma").click()
        count(2)
        button("DEMO-Beta").click()
        count(3)
        reset()
        choose("subgroups", "DEMO-Alpha, with comma")
        count(2)
        reset()
        driver.execute_script(
            (root / "analysis_lister/views/assets/gal-ongoing.js").read_text()
        )
        choose("subgroups", "DEMO-Beta")
        count(2)
        reset()
        assert driver.execute_script(
            "return getComputedStyle(document.querySelector('.gal-progress')).flexDirection === 'row'"
        )
        driver.save_screenshot(str(work_dir / "desktop.png"))
        driver.set_window_size(390, 1000)
        assert driver.execute_script(
            "return document.documentElement.scrollWidth <= window.innerWidth"
        )
        driver.save_screenshot(str(work_dir / "mobile.png"))
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
        driver.refresh()
        assert (
            len(
                [
                    x
                    for x in driver.find_elements(By.CSS_SELECTOR, "[data-gal-item]")
                    if x.is_displayed()
                ]
            )
            == 4
        )
        assert not driver.find_element(
            By.CSS_SELECTOR, "[data-gal-controls]"
        ).is_displayed()
        assert driver.find_element(
            By.CSS_SELECTOR, "[data-gal-item] .gal-progress"
        ).is_displayed()
        assert driver.execute_script(
            "const flow=document.querySelector('.gal-progress'); const steps=Array.from(flow.children); return getComputedStyle(flow).flexDirection==='column' && new Set(steps.map(e=>Math.round(e.getBoundingClientRect().x))).size===1 && steps.every((e,i)=>i===0 || e.getBoundingClientRect().y>steps[i-1].getBoundingClientRect().bottom)"
        )
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-gal-item]")
        assert len({round(card.rect["x"]) for card in cards}) == 1
        print(
            "Browser checks passed: OR/AND filters, search, reset, keyboard, instant replacement, idempotence, mobile overflow and no-JavaScript fallback."
        )


def main():
    with TemporaryDirectory(prefix="gal-ongoing-browser-") as directory:
        run_checks(Path(directory))


if __name__ == "__main__":
    main()
