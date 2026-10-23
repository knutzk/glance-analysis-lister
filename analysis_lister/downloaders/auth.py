# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Saved credentials and explicit browser login for the HTML downloader."""

import json
import logging
from pathlib import Path

from .http import URLS

logger = logging.getLogger(__name__)


class CookieManager:
    @staticmethod
    def load_cookies(cookie_file: Path):
        """Load cookies from a JSON file if available."""
        if cookie_file.exists():
            logger.debug(f"Loading cookies from {cookie_file}")
            return json.loads(cookie_file.read_text())
        logger.debug("No cookie file found.")
        return None

    @staticmethod
    def save_cookies(cookies, cookie_file: Path):
        """Save cookies to a JSON file."""
        cookie_file.write_text(json.dumps(cookies))
        logger.debug(f"Cookies successfully saved to {cookie_file}")

    @staticmethod
    def generate_cookies(cookie_file: Path):
        """Use Selenium to retrieve new cookies after logging in manually."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        logger.info("Starting Selenium to retrieve new cookies.")
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(), options=chrome_options)
        try:
            url = URLS["analyses"]
            logger.info(f"Opening URL: {url}")
            driver.get(url)
            logger.info("Please log in manually if required.")
            input("Press Enter after completing login...")
            cookies = driver.get_cookies()
            CookieManager.save_cookies(cookies, cookie_file)
            return cookies
        finally:
            driver.quit()
            logger.debug("Selenium session ended.")

    @staticmethod
    def to_requests_format(cookies):
        """Convert cookies from Selenium format to Requests format."""
        logger.debug("Converting cookies to Requests-compatible format.")
        return {cookie["name"]: cookie["value"] for cookie in cookies}


def resolve_cookies(
    cookie_file: Path, *, generate_new_cookies: bool = False
) -> dict[str, str]:
    """Load or generate credentials for a live download."""
    cookies = (
        CookieManager.generate_cookies(cookie_file)
        if generate_new_cookies
        else CookieManager.load_cookies(cookie_file)
    )
    if not cookies:
        raise ValueError("No cookies found. Use --login.")
    return CookieManager.to_requests_format(cookies)
