"""Script to download CSV files for analysis lister.

This script fetches data from specified URLs, parses HTML table data, and
saves it to CSV files. It uses cookies for authentication and can generate
new cookies using Selenium if needed.
"""

import argparse
import csv
import json
import logging
import requests
import sys
import urllib3
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from analysis_lister.glance.analysis import ANALYSIS_DATA_COLUMNS
from analysis_lister.glance.paper import PAPER_DATA_COLUMNS

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
    def fix_malformed_td(html):
        """Fix malformed <td> tags where the closing </td> is missing."""
        import re

        # Look for <td> tags that do not have a closing tag
        malformed_td_pattern = r"(<td>.*?)(?=<td>)"
        fixed_html = re.sub(malformed_td_pattern, r"\1</td>", html, flags=re.DOTALL)
        fixed_html = fixed_html.replace("\n", " ")

        return fixed_html

    @staticmethod
    def parse_to_csv(html, output_csv, debug_filename=None, column_filter=None):
        """Parse the HTML table data and save it to a CSV file."""
        logging.info(f"Parsing HTML content to extract table data for {output_csv}")

        # Fix malformed <td> tags (glance tables seem to have a lot of these).
        html = HTMLParser.fix_malformed_td(html)

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if not table:
            logging.error(f"No table found in the HTML for {output_csv}")
            raise ValueError("No table found")

        if debug_filename:
            DEBUG_DIR.mkdir(exist_ok=True)
            debug_path = DEBUG_DIR / debug_filename
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(str(table) + "\n")
            logging.debug(f"All table rows saved to {debug_path}")

        rows = table.find_all("tr")

        headers = [th.text.strip() for th in rows[0].find_all("th")]

        # Filter headers based on the column_filter, otherwise include all.
        if column_filter:
            header_indices = {
                index: header
                for index, header in enumerate(headers)
                if header in column_filter
            }
            logging.info(f"Filtering columns: {list(header_indices.values())}")
        else:
            header_indices = {index: header for index, header in enumerate(headers)}

        csv_data = [[header_indices[idx] for idx in header_indices]]

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue

            csv_data.append(
                [cells[idx].text for idx in header_indices if idx < len(cells)]
            )

        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)

        logging.info(f"CSV file successfully generated: {output_csv}")


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
            "column_filter": ANALYSIS_DATA_COLUMNS,
        },
        {
            "name": "papers",
            "url": URLS["papers"],
            "output_csv": CSV_DIR / "papers.csv",
            "debug_file": "papers.html",
            "column_filter": PAPER_DATA_COLUMNS,
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
            html,
            task["output_csv"],
            task["debug_file"] if args.debug else None,
            task["column_filter"],
        )


if __name__ == "__main__":
    main()
