# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Keyboard and layout regressions for rendered collections in their host theme."""

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

COLLECTION = ".gal-collection"
TOGGLE = "[data-gal-card-toggle], [data-gal-paper-toggle], [data-gal-note-toggle]"
COLLAPSE = (
    "[data-gal-card-collapse], [data-gal-paper-collapse], [data-gal-note-collapse]"
)
RESET = "[data-gal-reset], [data-gal-note-reset]"
EXPAND = "[data-gal-expand-all], [data-gal-archive-expand-all]"


def press(driver, *keys):
    ActionChains(driver).send_keys(*keys).perform()


def tab_to(driver, target):
    """Reach an element by actual sequential navigation, without JS focus/click."""
    for _ in range(160):
        if driver.switch_to.active_element == target:
            return
        press(driver, Keys.TAB)
    raise AssertionError(
        f"Unreachable by Tab: {target.tag_name} {target.accessible_name}"
    )


def assert_focus(driver, element):
    assert driver.switch_to.active_element == element
    assert element.accessible_name.strip(), element.tag_name
    visible = driver.execute_script(
        "const e=arguments[0], s=getComputedStyle(e);"
        "return e.matches(':focus-visible') && s.outlineStyle !== 'none' && "
        "parseFloat(s.outlineWidth) >= 2 && s.outlineColor !== 'transparent' && "
        "s.outlineColor !== 'rgba(0, 0, 0, 0)';",
        element,
    )
    assert visible, (
        f"Missing focus indicator: {element.tag_name} {element.accessible_name}"
    )


def check_keyboard(driver, wait, page):
    root = driver.find_element(By.CSS_SELECTOR, COLLECTION)
    counter = root.find_element(By.CSS_SELECTOR, '[role="status"]')
    assert counter.get_attribute("aria-live") == "polite"
    assert counter.get_attribute("aria-atomic") == "true"
    for element in root.find_elements(
        By.CSS_SELECTOR, "button, input, select, [tabindex]"
    ):
        if element.is_displayed() and element.is_enabled():
            assert element.accessible_name.strip(), element.get_attribute("outerHTML")
    search = root.find_element(By.CSS_SELECTOR, "[data-gal-search]")
    tab_to(driver, search)
    assert_focus(driver, search)
    press(driver, Keys.TAB)
    assert driver.switch_to.active_element != search
    ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.TAB).key_up(
        Keys.SHIFT
    ).perform()
    assert_focus(driver, search)
    press(driver, "no-synthetic-record-matches")
    wait.until(lambda _: counter.text.startswith("0 of 4"))
    assert not root.find_element(By.CSS_SELECTOR, EXPAND).is_enabled()
    reset = root.find_element(By.CSS_SELECTOR, RESET)
    tab_to(driver, reset)
    assert_focus(driver, reset)
    press(driver, Keys.SPACE)
    default_count = 3 if page in {"confnotes", "pubnotes"} else 4
    wait.until(lambda _: counter.text.startswith(f"{default_count} of 4"))
    assert driver.switch_to.active_element == reset

    choice = root.find_element(
        By.CSS_SELECTOR, "[data-gal-value], [data-gal-note-supersession]"
    )
    tab_to(driver, choice)
    assert_focus(driver, choice)
    before = choice.get_attribute("aria-pressed")
    press(driver, Keys.SPACE)
    wait.until(lambda _: choice.get_attribute("aria-pressed") != before)
    press(driver, Keys.ENTER)
    wait.until(lambda _: choice.get_attribute("aria-pressed") == before)
    for field in root.find_elements(By.CSS_SELECTOR, 'select, input[type="month"]'):
        tab_to(driver, field)
        assert_focus(driver, field)
        if field.tag_name == "select":
            # Native type-ahead selects "Analysis identifier" without an OS popup.
            field.send_keys("a", Keys.ENTER)
            wait.until(
                lambda _, field=field: field.get_attribute("value") == "reference"
            )
            assert "sort=reference" in driver.current_url
            tab_to(driver, reset)
            press(driver, Keys.SPACE)

    expand = root.find_element(By.CSS_SELECTOR, EXPAND)
    tab_to(driver, expand)
    assert_focus(driver, expand)
    press(driver, Keys.ENTER)
    wait.until(lambda _: expand.get_attribute("aria-pressed") == "true")
    press(driver, Keys.SPACE)
    wait.until(lambda _: expand.get_attribute("aria-pressed") == "false")

    toggle = next(
        e for e in root.find_elements(By.CSS_SELECTOR, TOGGLE) if e.is_displayed()
    )
    tab_to(driver, toggle)
    assert_focus(driver, toggle)
    assert toggle.get_attribute("role") == "button"
    panel = driver.find_element(By.ID, toggle.get_attribute("aria-controls"))
    assert not panel.is_displayed()
    press(driver, Keys.ENTER)
    wait.until(lambda _: panel.is_displayed())
    assert toggle.get_attribute("aria-expanded") == "true"
    collapse = panel.find_element(By.CSS_SELECTOR, COLLAPSE)
    tab_to(driver, collapse)
    assert_focus(driver, collapse)
    press(driver, Keys.SPACE)
    wait.until(lambda _: not panel.is_displayed())
    assert toggle.get_attribute("aria-expanded") == "false"
    assert_focus(driver, toggle)


def check_layout_and_fallback(driver, wait, base, page_prefix, *, keyboard=True):
    """Check host layouts and static content at actual CSS viewport sizes.

    Full suites additionally traverse and scroll regions with the keyboard.
    Hosting checks keep all viewport, colour-scheme and static-content assertions.
    """
    try:
        for width in (390, 320):
            driver.execute_cdp_cmd(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": 900,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            for page in ("ongoing", "papers", "confnotes", "pubnotes"):
                driver.get(base + f"{page_prefix}{page}/")
                root = driver.find_element(By.CSS_SELECTOR, COLLECTION)
                wait.until(
                    lambda _, root=root: root.find_element(
                        By.CSS_SELECTOR, "[data-gal-search]"
                    ).is_displayed()
                )
                for scheme in ("default", "slate"):
                    driver.execute_script(
                        "document.body.setAttribute('data-md-color-scheme', arguments[0])",
                        scheme,
                    )
                    assert driver.execute_script(
                        "return document.documentElement.scrollWidth <= innerWidth"
                    ), (page, width, scheme)
                    if keyboard:
                        search = root.find_element(By.CSS_SELECTOR, "[data-gal-search]")
                        tab_to(driver, search)
                        assert_focus(driver, search)
                        for region in root.find_elements(
                            By.CSS_SELECTOR, ".gal-table-scroll"
                        ):
                            tab_to(driver, region)
                            assert_focus(driver, region)
                            if driver.execute_script(
                                "return arguments[0].scrollWidth > arguments[0].clientWidth",
                                region,
                            ):
                                driver.execute_script(
                                    "arguments[0].scrollLeft=0", region
                                )
                                press(driver, Keys.ARROW_RIGHT)
                                wait.until(
                                    lambda _, region=region: driver.execute_script(
                                        "return arguments[0].scrollLeft > 0", region
                                    )
                                )
                driver.execute_cdp_cmd(
                    "Emulation.setScriptExecutionDisabled", {"value": True}
                )
                driver.refresh()
                root = driver.find_element(By.CSS_SELECTOR, COLLECTION)
                records = root.find_elements(
                    By.CSS_SELECTOR, "[data-gal-item], [data-gal-note]"
                )
                assert len(records) == 4 and all(e.is_displayed() for e in records)
                assert not root.find_element(
                    By.CSS_SELECTOR, "[data-gal-search]"
                ).is_displayed()
                for toggle in root.find_elements(By.CSS_SELECTOR, TOGGLE):
                    panel = driver.find_element(
                        By.ID, toggle.get_attribute("aria-controls")
                    )
                    assert panel.is_displayed() and panel.text.strip()
                    assert toggle.get_attribute("tabindex") is None
                assert driver.execute_script(
                    "return document.documentElement.scrollWidth <= innerWidth"
                ), (page, width, "static")
                driver.execute_cdp_cmd(
                    "Emulation.setScriptExecutionDisabled", {"value": False}
                )
    finally:
        driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": False})
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
