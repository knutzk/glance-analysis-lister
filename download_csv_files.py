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
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from analysis_lister.glance import field_maps
from analysis_lister.storage import CSV_REFRESH_MARKER, atomic_write_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
COOKIE_FILE = Path("cookies.json")
CSV_DIR = Path("deploy_tools/analysis_lists/csv")
DEBUG_DIR = Path("debug")
REQUEST_TIMEOUT = (10, 30)  # Connection timeout, then socket read timeout (seconds).
INTERMEDIATE_CA = (
    Path(__file__).resolve().parent
    / "certs/sectigo-public-server-authentication-ca-ov-r36.pem"
)
URLS = {
    "analyses": "https://atlas-glance.cern.ch/atlas/analysis/analyses/main.php",
    "papers": "https://atlas-glance.cern.ch/atlas/analysis/papers/main.php",
    "pubnotes": "https://atlas-glance.cern.ch/atlas/analysis/pubnotes/main.php",
    "confnotes": "https://atlas-glance.cern.ch/atlas/analysis/confnotes/main.php",
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
    "s[0][descending]": "false",
    "only_deleted_input": "false",
}


@contextmanager
def trusted_ca_bundle():
    """Complete GLANCE's chain without disabling certificate verification.

    Preserve Requests' CA-bundle environment overrides. Otherwise supplement
    its trusted roots with the intermediate GLANCE currently omits. The
    temporary bundle stays available until the request and redirects finish.
    """
    override = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    if override:
        yield override
        return

    with NamedTemporaryFile(suffix=".pem") as bundle:
        bundle.write(Path(requests.certs.where()).read_bytes())
        bundle.write(b"\n")
        bundle.write(INTERMEDIATE_CA.read_bytes())
        bundle.flush()
        yield bundle.name


class CookieManager:
    @staticmethod
    def load_cookies():
        """Load cookies from a JSON file if available."""
        if COOKIE_FILE.exists():
            logger.info(f"Loading cookies from {COOKIE_FILE}")
            return json.loads(COOKIE_FILE.read_text())
        logger.info("No cookie file found.")
        return None

    @staticmethod
    def save_cookies(cookies):
        """Save cookies to a JSON file."""
        COOKIE_FILE.write_text(json.dumps(cookies))
        logger.info(f"Cookies successfully saved to {COOKIE_FILE}")

    @staticmethod
    def generate_cookies():
        """Use Selenium to retrieve new cookies after logging in manually."""
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
            CookieManager.save_cookies(cookies)
            return cookies
        finally:
            driver.quit()
            logger.info("Selenium session ended.")

    @staticmethod
    def to_requests_format(cookies):
        """Convert cookies from Selenium format to Requests format."""
        logger.info("Converting cookies to Requests-compatible format.")
        return {cookie["name"]: cookie["value"] for cookie in cookies}


class DataFetcher:
    @staticmethod
    def fetch_html(url, params, cookies):
        """Fetch HTML content from a URL."""
        try:
            logger.info(f"Fetching data from {url} with params: {params}")
            with trusted_ca_bundle() as ca_bundle:
                response = requests.get(
                    url,
                    params=params,
                    cookies=cookies,
                    verify=ca_bundle,
                    timeout=REQUEST_TIMEOUT,
                )
            response.raise_for_status()
            if "Sign in to your account" in response.text:
                logger.error("Invalid or expired cookies detected.")
                sys.exit(1)
            return response.text
        except requests.exceptions.SSLError:
            logger.error(
                "TLS verification failed for %s. Check the server certificate "
                "chain or supply a trusted PEM bundle with REQUESTS_CA_BUNDLE.",
                url,
            )
            raise
        except requests.RequestException as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise


class HTMLParser:
    @staticmethod
    def fix_malformed_td(html):
        """Fix malformed <td> tags where the closing </td> is missing."""
        import re

        # Look for <td> tags that do not have a closing tag
        malformed_td_pattern = r"(<td>.*?)(?=<td>)"
        fixed_html = re.sub(malformed_td_pattern, r"\1</td>", html, flags=re.DOTALL)
        return fixed_html.replace("\n", " ")

    @staticmethod
    def parse_to_csv(html, output_csv, debug_filename=None, column_filter=None):
        """Parse the HTML table data and save it to a CSV file."""
        logger.info(f"Parsing HTML content to extract table data for {output_csv}")

        # Fix malformed <td> tags (glance tables seem to have a lot of these).
        html = HTMLParser.fix_malformed_td(html)

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if not table:
            logger.error(f"No table found in the HTML for {output_csv}")
            raise ValueError("No table found")

        if debug_filename:
            DEBUG_DIR.mkdir(exist_ok=True)
            debug_path = DEBUG_DIR / debug_filename
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(str(table) + "\n")
            logger.debug(f"All table rows saved to {debug_path}")

        rows = table.find_all("tr")
        if not rows:
            raise ValueError(f"No rows in table for {output_csv}")

        headers = [th.text.strip() for th in rows[0].find_all("th")]

        # Filter headers based on the column_filter, otherwise include all.
        if column_filter:
            # A column that GLANCE has renamed would silently turn into an
            # empty field for every single entry, so stop right here.
            missing = sorted({col for col in column_filter if col not in headers})
            if missing:
                logger.error(
                    f"Columns missing from the table for {output_csv}: {missing}. "
                    "GLANCE has probably renamed them; update the field maps in "
                    "analysis_lister/glance/field_maps.py."
                )
                raise ValueError(f"Missing columns for {output_csv}: {missing}")

            header_indices = {
                index: header
                for index, header in enumerate(headers)
                if header in column_filter
            }
            logger.info(f"Filtering columns: {list(header_indices.values())}")
        else:
            header_indices = dict(enumerate(headers))

        csv_data = [[header_indices[idx] for idx in header_indices]]

        n_short_rows = 0
        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue

            # Short rows are padded rather than shortened, which would shift
            # the remaining values into the wrong columns.
            if len(cells) < len(headers):
                n_short_rows += 1

            csv_data.append(
                [cells[idx].text if idx < len(cells) else "" for idx in header_indices]
            )

        if n_short_rows:
            logger.warning(
                f"{n_short_rows} rows of the table for {output_csv} have fewer "
                f"cells than the {len(headers)} of its header. Their missing "
                "values were left empty; check the table in GLANCE."
            )

        if len(csv_data) == 1:
            raise ValueError(f"No data rows in table for {output_csv}")

        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)

        logger.info(f"CSV file successfully generated: {output_csv}")


def publish_csv_batch(
    staging: Path,
    output_dir: Path,
    filenames: list[str],
    *,
    snapshot_path: Path | None = None,
):
    """Publish a validated batch, restoring the old files on a write failure.

    The marker makes an interrupted promotion detectable by the registry loader.
    Backups remain in the staging directory if the process is killed outright.
    A fresh successful download repairs such an interrupted promotion.
    An optional staged JSON snapshot is published last using an atomic write.
    If that write fails, the CSV replacements are rolled back too.
    Run downloading and registry building sequentially.
    """
    backup = staging / "previous"
    backup.mkdir()
    for name in filenames:
        old = output_dir / name
        if old.exists():
            shutil.copy2(old, backup / name)

    marker = output_dir / CSV_REFRESH_MARKER
    was_interrupted = marker.exists()
    marker.write_text("Refresh incomplete; re-run refresh_analysis_lists.py.\n")
    replaced = []
    try:
        for name in filenames:
            replaced.append(name)
            (staging / name).replace(output_dir / name)
        if snapshot_path is not None:
            atomic_write_text(
                snapshot_path, (staging / snapshot_path.name).read_text(encoding="utf8")
            )
    except BaseException:
        for name in reversed(replaced):
            previous = backup / name
            if previous.exists():
                previous.replace(output_dir / name)
            else:
                (output_dir / name).unlink(missing_ok=True)
        if not was_interrupted:
            marker.unlink()
        raise
    marker.unlink()


@contextmanager
def staged_csv_files(tasks, *, cookies=None, use_local_html=False, debug=False):
    """Yield a complete CSV batch without modifying the current data."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so individual replacements are atomic.
    temporary = TemporaryDirectory(prefix=".refresh-", dir=CSV_DIR, delete=False)
    staging = Path(temporary.name)
    try:
        for task in tasks:
            if use_local_html:
                html = (DEBUG_DIR / task["debug_file"]).read_text(encoding="utf-8")
            else:
                html = DataFetcher.fetch_html(
                    task["url"], COMMON_PARAMS | task["custom_params"], cookies
                )
            HTMLParser.parse_to_csv(
                html,
                staging / task["output_csv"].name,
                task["debug_file"] if debug and not use_local_html else None,
                task["column_filter"],
            )
        yield staging
    finally:
        if (CSV_DIR / CSV_REFRESH_MARKER).exists():
            logger.warning("Incomplete refresh; retaining staging files at %s", staging)
        else:
            temporary.cleanup()


def refresh_csv_files(tasks, **options):
    """Fetch and publish CSVs only, for the standalone download command."""
    with staged_csv_files(tasks, **options) as staging:
        publish_csv_batch(staging, CSV_DIR, [t["output_csv"].name for t in tasks])
    logger.info("Published complete CSV batch.")


def add_download_arguments(parser):
    """Share download options with the combined refresh command."""
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


def download_tasks():
    """Return the four GLANCE table definitions."""
    return [
        {
            "name": "analyses",
            "url": URLS["analyses"],
            "output_csv": CSV_DIR / "analyses.csv",
            "debug_file": "analyses.html",
            "column_filter": field_maps.REQUIRED_COLUMNS_ANALYSIS,
            "custom_params": {"s[0][name]": "reference_code"},
        },
        {
            "name": "papers",
            "url": URLS["papers"],
            "output_csv": CSV_DIR / "papers.csv",
            "debug_file": "papers.html",
            "column_filter": field_maps.REQUIRED_COLUMNS_PAPER,
            "custom_params": {"s[0][name]": "reference_code"},
        },
        {
            "name": "pubnotes",
            "url": URLS["pubnotes"],
            "output_csv": CSV_DIR / "pubnotes.csv",
            "debug_file": "pubnotes.html",
            "column_filter": field_maps.REQUIRED_COLUMNS_PUBNOTE,
            "custom_params": {"s[0][name]": "final_ref_code"},
        },
        {
            "name": "confnotes",
            "url": URLS["confnotes"],
            "output_csv": CSV_DIR / "confnotes.csv",
            "debug_file": "confnotes.html",
            "column_filter": field_maps.REQUIRED_COLUMNS_CONFNOTE,
            "custom_params": {"s[0][name]": "final_ref_code"},
        },
    ]


def download_options(args):
    """Resolve authentication only for live downloads."""
    if args.use_local_html:
        return {"use_local_html": True}

    if args.generate_new_cookies:
        cookies = CookieManager.generate_cookies()
    else:
        cookies = CookieManager.load_cookies()
        if not cookies:
            logger.error("No cookies found. Use --generate-new-cookies.")
            sys.exit(1)

    return {"cookies": CookieManager.to_requests_format(cookies), "debug": args.debug}


def main():
    parser = argparse.ArgumentParser(description="Fetch data and generate CSV files.")
    add_download_arguments(parser)
    args = parser.parse_args()
    refresh_csv_files(download_tasks(), **download_options(args))


if __name__ == "__main__":
    main()
