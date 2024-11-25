"""Script to download CSV files for analysis lister.

This script fetches data from specified URLs, parses HTML table data, and
saves it to CSV files. It uses cookies for authentication and can generate
new cookies using Selenium if needed.
"""

import argparse
import csv
import json
import logging
import os
import sys
import urllib3
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Constants
COOKIE_FILE = Path("cookies.json")
CSV_DIR = Path("csv")
DEBUG_DIR = Path("debug")
URLS = {
    "analyses": "https://atlas-glance.cern.ch/atlas/analysis/analyses/main.php",
    "papers": "https://atlas-glance.cern.ch/atlas/analysis/papers/main.php",
}
COMMON_PARAMS = {
    "c[0][i]": 0,
    "c[0][p]": "subgroups",
    "c[0][o]": "contains",
    "c[0][v]": 80,
    "c[1][i]": 1,
    "c[1][p]": "subgroups",
    "c[1][o]": "contains",
    "c[1][v]": 198,
    "c[2][i]": 2,
    "c[2][p]": "subgroups",
    "c[2][o]": "contains",
    "c[2][v]": 205,
    "s[0][name]": "reference_code",
    "s[0][descending]": "false",
    "only_deleted_input": "false",
}
COLUMN_FILTER_ANALYSES = {
    "Reference Code": None,
    "Short Title": None,
    "Public Short Title": None,
    "Full Title": None,
    "Status": None,
    "Run": None,
    "Leading Group": None,
    "Subgroups": None,
    "Contact Editors": None,
    "Supporting Documents": None,
    "Keywords": None,
    "Phase State": None,
    "Phase 0 Start Date": None,
    "Analysis Contacts": None,
    "Analysis Contacts' Start Date": None,
    "Analysis Contacts' End Date": None,
    "Internal Note Editors": None,
    "Editorial Board": None,
    "Chairs": None,
    "Editorial Board Formed On": None,
    "Pre approval Meetings Dates": None,
    "Approval Meetings Dates": None,
}

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CookieManager:
    @staticmethod
    def load_cookies():
        """Load cookies from a JSON file if available."""
        if COOKIE_FILE.exists():
            logging.info(f"Loading cookies from {COOKIE_FILE}")
            return json.loads(COOKIE_FILE.read_text())
        logging.info("No cookie file found.")
        return None

    @staticmethod
    def save_cookies(cookies):
        """Save cookies to a JSON file."""
        COOKIE_FILE.write_text(json.dumps(cookies))
        logging.info(f"Cookies successfully saved to {COOKIE_FILE}")

    @staticmethod
    def generate_cookies():
        """Use Selenium to retrieve new cookies after logging in manually."""
        logging.info("Starting Selenium to retrieve new cookies.")
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(), options=chrome_options)
        try:
            url = URLS["analyses"]
            logging.info(f"Opening URL: {url}")
            driver.get(url)
            logging.info("Please log in manually if required.")
            input("Press Enter after completing login...")
            cookies = driver.get_cookies()
            CookieManager.save_cookies(cookies)
            return cookies
        finally:
            driver.quit()
            logging.info("Selenium session ended.")

    @staticmethod
    def to_requests_format(cookies):
        """Convert cookies from Selenium format to Requests format."""
        logging.info("Converting cookies to Requests-compatible format.")
        return {cookie["name"]: cookie["value"] for cookie in cookies}


class DataFetcher:
    @staticmethod
    def fetch_html(url, params, cookies):
        """Fetch HTML content from a URL."""
        try:
            logging.info(f"Fetching data from {url} with params: {params}")
            response = requests.get(url, params=params, cookies=cookies, verify=False)
            response.raise_for_status()
            if "Sign in to your account" in response.text:
                logging.error("Invalid or expired cookies detected.")
                sys.exit(1)
            return response.text
        except requests.RequestException as e:
            logging.error(f"Error fetching data from {url}: {e}")
            raise


class HTMLParser:
    @staticmethod
    def parse_to_csv(html, output_csv, debug_file=None, column_filter=None):
        """Parse HTML and save table data to CSV."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            raise ValueError("No table found in the HTML.")

        if debug_file:
            DEBUG_DIR.mkdir(exist_ok=True)
            debug_path = DEBUG_DIR / debug_file
            debug_path.write_text(str(table), encoding="utf-8")
            logging.info(f"Debug file saved: {debug_path}")

        rows = table.find_all("tr")
        headers = [th.text.strip() for th in rows[0].find_all("th")]

        if column_filter:
            indices = {
                idx: header
                for idx, header in enumerate(headers)
                if header in column_filter
            }
        else:
            indices = {idx: header for idx, header in enumerate(headers)}

        csv_data = [[indices[idx] for idx in indices]]
        csv_data += [
            [row.find_all("td")[idx].text.strip() for idx in indices]
            for row in rows[1:]
            if row.find_all("td")
        ]

        CSV_DIR.mkdir(exist_ok=True)
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)
        logging.info(f"CSV file saved: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Fetch data and generate CSV files.")
    parser.add_argument(
        "--generate-new-cookies",
        action="store_true",
        help="Generate new cookies using Selenium.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save raw HTML tables to debug directory.",
    )
    parser.add_argument(
        "--use-local-html",
        action="store_true",
        help="Read HTML from debug directory instead of fetching it.",
    )
    args = parser.parse_args()

    tasks = [
        {
            "name": "analyses",
            "url": URLS["analyses"],
            "output_csv": CSV_DIR / "analyses.csv",
            "debug_file": "analyses.html",
            "column_filter": COLUMN_FILTER_ANALYSES,
        },
        {
            "name": "papers",
            "url": URLS["papers"],
            "output_csv": CSV_DIR / "papers.csv",
            "debug_file": "papers.html",
            "column_filter": None,
        },
    ]

    cookies = None
    if args.use_local_html:
        for task in tasks:
            html = (DEBUG_DIR / task["debug_file"]).read_text(encoding="utf-8")
            HTMLParser.parse_to_csv(
                html, task["output_csv"], None, task["column_filter"]
            )
        logging.info("Completed processing from local HTML files.")
        return

    if args.generate_new_cookies:
        cookies = CookieManager.generate_cookies()
    else:
        cookies = CookieManager.load_cookies()
        if not cookies:
            logging.error("No cookies found. Use --generate-new-cookies.")
            sys.exit(1)

    cookies = CookieManager.to_requests_format(cookies)
    for task in tasks:
        html = DataFetcher.fetch_html(task["url"], COMMON_PARAMS, cookies)
        HTMLParser.parse_to_csv(
            html, task["output_csv"], task["debug_file"] if args.debug else None, task["column_filter"]
        )


if __name__ == "__main__":
    main()
