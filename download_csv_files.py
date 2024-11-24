"""Script to download CSV files for analysis lister.

This script fetches data from specified URLs, parses HTML table data, and
saves it to CSV files. It uses cookies for authentication and can generate
new cookies using Selenium if needed.

"""

import argparse
from bs4 import BeautifulSoup
import csv
import json
import logging
import requests
import sys
from pathlib import Path
import urllib3

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


def fetch_data(url, params, cookies):
    """Fetch data from a given URL using a GET request."""
    try:
        logging.info(f"Fetching data from {url} with params: {params}")
        response = requests.get(url, params=params, cookies=cookies, verify=False)
        response.raise_for_status()
        if "Sign in to your account" in response.text:
            logging.error(
                "Cookies are invalid or expired. Run the script with "
                "--generate-new-cookies to fetch new cookies."
            )
            sys.exit(1)
        logging.info(f"Successfully fetched data from {url}")
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise


def parse_html_to_csv(html, output_csv):
    """Parse the HTML table data and save it to a CSV file."""
    logging.info(f"Parsing HTML content to extract table data for {output_csv}")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        logging.error(f"No table found in the HTML for {output_csv}")
        raise ValueError("No table found")

    rows = table.find_all("tr")
    csv_data = [
        [
            col.text.replace("\n", " ").replace("\r", " ")
            for col in row.find_all(["td", "th"])
        ]
        for row in rows
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(csv_data)

    logging.info(f"CSV file successfully generated: {output_csv}")


def load_cookies():
    """Load cookies from a JSON file if available."""
    if COOKIE_FILE.exists():
        logging.info(f"Loading cookies from {COOKIE_FILE}")
        return json.loads(COOKIE_FILE.read_text())
    logging.info("No cookie file found.")
    return None


def get_new_cookies():
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
        COOKIE_FILE.write_text(json.dumps(cookies))
        logging.info(f"Cookies successfully saved to {COOKIE_FILE}")
        return cookies
    finally:
        driver.quit()
        logging.info("Selenium session ended.")


def cookies_to_dict(cookies):
    """Convert cookies from Selenium format to Requests format."""
    logging.info("Converting cookies to Requests-compatible format.")
    return {cookie["name"]: cookie["value"] for cookie in cookies}


def process_request(url, params, cookies, output_csv):
    """Process a single URL request and save results to a CSV file."""
    logging.info(f"Processing request for {output_csv}.")
    try:
        html = fetch_data(url, params, cookies)
        parse_html_to_csv(html, output_csv)
    except Exception as e:
        logging.error(f"Failed to process request for {output_csv}: {e}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Fetch data and generate CSV files.")
    parser.add_argument(
        "--generate-new-cookies",
        action="store_true",
        help="Use Selenium to generate new cookies and save them to the file.",
    )
    args = parser.parse_args()

    # Ensure the output directory exists
    CSV_DIR.mkdir(exist_ok=True)

    # Load or generate cookies
    if args.generate_new_cookies:
        logging.info("Generating new cookies as requested.")
        cookies = cookies_to_dict(get_new_cookies())
    else:
        cookies = load_cookies()
        if not cookies:
            logging.error(
                "No cookie file found. Run the script with --generate-new-cookies to generate new cookies."
            )
            sys.exit(1)
        cookies = cookies_to_dict(cookies)

    # Define tasks
    tasks = [
        {"url": URLS["analyses"], "output_csv": CSV_DIR / "analyses.csv"},
        {"url": URLS["papers"], "output_csv": CSV_DIR / "papers.csv"},
    ]

    # Process each task
    for task in tasks:
        process_request(task["url"], COMMON_PARAMS, cookies, task["output_csv"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
