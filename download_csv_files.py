import logging
import requests
from bs4 import BeautifulSoup
import csv
import os
import json
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

logging.basicConfig(level=logging.INFO)

COOKIE_FILE = "cookies.json"

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_data(url, params, cookies):
    """
    Send a GET request and fetch the HTML response.
    """
    try:
        response = requests.get(url, params=params, cookies=cookies, verify=False)
        response.raise_for_status()
        logging.info(f"Successfully fetched data from {url}")
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise


def parse_html_to_csv(html, output_csv):
    """
    Parse the HTML table data and save it to a CSV file.
    """
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

    logging.info(f"CSV file generated: {output_csv}")


def load_cookies():
    """
    Load cookies from a JSON file if available.
    """
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            logging.info("Loading cookies from file")
            return json.load(f)
    return None


def save_cookies(cookies):
    """
    Save cookies to a JSON file.
    """
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f)
        logging.info("Cookies saved to file")


def get_new_cookies():
    """
    Use Selenium to retrieve new cookies after logging in manually.
    """
    logging.info("Starting Selenium to retrieve new cookies")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    try:
        driver.get("https://atlas-glance.cern.ch/atlas/analysis/analyses/main.php")
        logging.info("Please log in manually if required.")
        input("Press Enter after completing login...")
        cookies = driver.get_cookies()
        save_cookies(cookies)
        return cookies
    finally:
        driver.quit()


def cookies_to_dict(cookies):
    """
    Convert cookies from Selenium format to Requests format.
    """
    return {cookie["name"]: cookie["value"] for cookie in cookies}


def validate_cookies(url, params, cookies):
    """
    Check if cookies are valid by making a test request and verifying the response content.
    """
    try:
        # Fetch the HTML response
        html = fetch_data(url, params, cookies)

        # Check for the string indicating a sign-in requirement
        if "Sign in to your account" in html:
            logging.warning("Cookies are invalid. Redirected to the login page.")
            return False
        else:
            logging.info("Cookies are valid.")
            return True
    except Exception as e:
        logging.warning(f"Cookies are invalid: {e}")
        return False


def process_request(url, params, cookies, output_csv):
    """
    Process a single URL request and save results to a CSV file.
    """
    try:
        html = fetch_data(url, params, cookies)
        parse_html_to_csv(html, output_csv)
    except Exception as e:
        logging.error(f"Failed to process request for {output_csv}: {e}")


def main():
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

    # Attempt to load cookies or fetch new ones if needed
    cookies = load_cookies()
    if cookies:
        cookies = cookies_to_dict(cookies)
        if not validate_cookies(tasks[0]["url"], common_params, cookies):
            cookies = cookies_to_dict(get_new_cookies())
    else:
        cookies = cookies_to_dict(get_new_cookies())

    # Process each task
    for task in tasks:
        process_request(task["url"], common_params, cookies, task["output_csv"])


if __name__ == "__main__":
    main()
