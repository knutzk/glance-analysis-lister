"""Script to download CSV files for analysis lister.

This script fetches data from specified URLs, parses HTML table data, and
saves it to CSV files. It uses cookies for authentication and can generate
new cookies using Selenium if needed.

Functions:
    fetch_data(url, params, cookies):
        Send a GET request and fetch the HTML response.

    parse_html_to_csv(html, output_csv):
        Parse the HTML table data and save it to a CSV file.

    load_cookies():
        Load cookies from a JSON file if available.

    get_new_cookies():
        Use Selenium to retrieve new cookies after logging in manually.

    cookies_to_dict(cookies):
        Convert cookies from Selenium format to Requests format.

    process_request(url, params, cookies, output_csv):
        Process a single URL request and save results to a CSV file.

    main():
        Main function to parse command-line arguments, load or generate
        cookies, and process tasks.

"""

import argparse
from bs4 import BeautifulSoup
import csv
import json
import logging
import requests
import os
import sys
import urllib3

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Configure logging with timestamps and log levels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

COOKIE_FILE = "cookies.json"

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_data(url, params, cookies):
    """Fetch data from a given URL using a GET request.

    Args:
        url (str): The URL to send the GET request to.
        params (dict): The parameters to include in the GET request.
        cookies (dict): The cookies to include in the GET request.

    Returns:
        str: The HTML response text from the GET request.

    Raises:
        SystemExit: If the response indicates that the cookies are invalid or expired.
        requests.RequestException: If there is an error during the GET request.

    Logs:
        Logs the URL and parameters when fetching data.
        Logs an error and exits if the cookies are invalid or expired.
        Logs an error if there is an error during the GET request.
        Logs a success message if data is fetched successfully.
    """
    try:
        logging.info(f"Fetching data from {url} with params: {params}")
        response = requests.get(url, params=params, cookies=cookies, verify=False)
        response.raise_for_status()
        response_text = response.text
        if "Sign in to your account" in response_text:
            logging.error(
                "Cookies are invalid or expired. Run the script with "
                "--generate-new-cookies to fetch new cookies."
            )
            sys.exit(1)
        logging.info(f"Successfully fetched data from {url}")
        return response_text
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise


def parse_html_to_csv(html, output_csv):
    """Parse the HTML table data and save it to a CSV file.

    Args:
        html (str): The HTML content containing the table data.
        output_csv (str): The file path where the CSV file will be saved.

    Raises:
        ValueError: If no table is found in the HTML content.

    """
    logging.info(f"Parsing HTML content to extract table data for {output_csv}")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        logging.error(f"No table found in the HTML for {output_csv}")
        raise ValueError("No table found")

    rows = table.find_all("tr")
    csv_data = [
        [
            col.text.replace("\n", " ").replace(
                "\r", " "
            )  # Replace line breaks with spaces
            for col in row.find_all(["td", "th"])
        ]
        for row in rows
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(csv_data)

    logging.info(f"CSV file successfully generated: {output_csv}")


def load_cookies():
    """Load cookies from a JSON file if available.

    This function checks if a cookie file exists at the specified path. If the
    file exists, it reads the file and loads the cookies from it. If the file
    does not exist, it logs a message indicating that no cookie file was found.

    Returns:
        dict: A dict containing the cookies if file exists, otherwise None.

    """
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            logging.info(f"Loading cookies from {COOKIE_FILE}")
            return json.load(f)

    logging.info("No cookie file found.")
    return None


def get_new_cookies():
    """Use Selenium to retrieve new cookies after logging in manually.

    This function launches a Selenium WebDriver instance with specified Chrome
    options, navigates to a given URL, and prompts the user to log in manually.
    After the login process is completed, it retrieves the cookies from the
    browser session and saves them to a specified file.

    Returns:
        list: A list of dictionaries, each representing a cookie retrieved
            from the browser session.

    Note:
        The user must manually log in to the website when prompted. The
        function will wait for the user to press Enter after completing the
        login process.

    """
    logging.info("Starting Selenium to retrieve new cookies.")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    try:
        url = "https://atlas-glance.cern.ch/atlas/analysis/analyses/main.php"
        logging.info(f"Opening URL: {url}")
        driver.get(url)
        logging.info("Please log in manually if required.")
        input("Press Enter after completing login...")
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
            logging.info(f"Cookies successfully saved to {COOKIE_FILE}")

        logging.info("New cookies retrieved and saved.")
        return cookies
    finally:
        driver.quit()
        logging.info("Selenium session ended.")


def cookies_to_dict(cookies):
    """Convert cookies from Selenium format to Requests format.

    Args:
        cookies (list): A list of dictionaries, where each dictionary
            represents a cookie with keys such as "name" and "value".

    Returns:
        dict: A dictionary where the keys are cookie names and the values
            are cookie values.

    """
    logging.info("Converting cookies to Requests-compatible format.")
    return {cookie["name"]: cookie["value"] for cookie in cookies}


def process_request(url, params, cookies, output_csv):
    """Process a single URL request and save results to a CSV file.

    Args:
        url (str): The URL to send the request to.
        params (dict): The parameters to include in the request.
        cookies (dict): The cookies to include in the request.
        output_csv (str): Path to output CSV file where results will be saved.

    """
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

    # Define common parameters
    common_params = {
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

    # Define tasks with unique URLs and output file names
    tasks = [
        {
            "url": "https://atlas-glance.cern.ch/atlas/analysis/analyses/main.php",
            "output_csv": "csv/analyses.csv",
        },
        {
            "url": "https://atlas-glance.cern.ch/atlas/analysis/papers/main.php",
            "output_csv": "csv/papers.csv",
        },
    ]

    # Check if cookies exist or if --generate-new-cookies is provided
    cookies = None
    if args.generate_new_cookies:
        logging.info("Generating new cookies as requested.")
        cookies = cookies_to_dict(get_new_cookies())
    else:
        cookies = load_cookies()
        if not cookies:
            logging.error(
                "No cookie file found. Run the script with "
                "--generate-new-cookies to generate new cookies."
            )
            sys.exit(1)

        cookies = cookies_to_dict(cookies)

    # Process each task
    for task in tasks:
        process_request(task["url"], common_params, cookies, task["output_csv"])


if __name__ == "__main__":
    main()
