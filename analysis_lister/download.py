"""Authenticated GLANCE downloads and staged HTML-to-CSV conversion."""

import csv
import json
import logging
import os
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import requests
from attrs import field, frozen

from analysis_lister.glance import field_maps
from analysis_lister.storage import CSV_REFRESH_MARKER

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = (10, 30)  # Connection timeout, then socket read timeout (seconds).
INTERMEDIATE_CA = (
    Path(__file__).resolve().parents[1]
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
    def load_cookies(cookie_file: Path):
        """Load cookies from a JSON file if available."""
        if cookie_file.exists():
            logger.info(f"Loading cookies from {cookie_file}")
            return json.loads(cookie_file.read_text())
        logger.info("No cookie file found.")
        return None

    @staticmethod
    def save_cookies(cookies, cookie_file: Path):
        """Save cookies to a JSON file."""
        cookie_file.write_text(json.dumps(cookies))
        logger.info(f"Cookies successfully saved to {cookie_file}")

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
                raise ValueError("Invalid or expired cookies detected.")
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
    def parse_to_csv(
        html, output_csv, debug_path: Path | None = None, column_filter=None
    ):
        """Parse the HTML table data and save it to a CSV file."""
        from bs4 import BeautifulSoup

        logger.info(f"Parsing HTML content to extract table data for {output_csv}")

        # Fix malformed <td> tags (glance tables seem to have a lot of these).
        html = HTMLParser.fix_malformed_td(html)

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if not table:
            logger.error(f"No table found in the HTML for {output_csv}")
            raise ValueError("No table found")

        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(str(table) + "\n")
            logger.debug(f"All table rows saved to {debug_path}")

        rows = table.find_all("tr")
        if not rows:
            raise ValueError(f"No rows in table for {output_csv}")

        headers = [th.text.strip() for th in rows[0].find_all("th")]
        selected = [h for h in headers if not column_filter or h in column_filter]
        duplicates = [h for h, n in Counter(selected).items() if n > 1]
        if not headers or any(not h for h in selected) or duplicates:
            raise ValueError(
                f"Invalid table headers for {output_csv}: duplicates={duplicates}"
            )

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

        for row_number, row in enumerate(rows[1:], start=2):
            cells = row.find_all("td")
            if not cells:
                continue

            if len(cells) != len(headers):
                raise ValueError(
                    f"{output_csv}: table row {row_number}: expected {len(headers)} "
                    f"cells, found {len(cells)}; cannot safely align the columns"
                )
            csv_data.append([cells[idx].text for idx in header_indices])

        if len(csv_data) == 1:
            raise ValueError(f"No data rows in table for {output_csv}")

        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)

        logger.info(f"CSV file successfully generated: {output_csv}")


@frozen
class DownloadTable:
    """GLANCE table metadata; destinations are supplied to the workflow separately."""

    name: str
    url: str
    columns: tuple[str, ...] = field(converter=tuple)
    sort_by: str

    @property
    def csv_filename(self) -> str:
        return f"{self.name}.csv"

    @property
    def html_filename(self) -> str:
        return f"{self.name}.html"


@contextmanager
def staged_csv_files(
    tasks: Sequence[DownloadTable],
    csv_dir: Path,
    debug_dir: Path,
    *,
    cookies: dict[str, str] | None = None,
    use_local_html: bool = False,
    debug: bool = False,
) -> Iterator[Path]:
    """Yield a complete CSV batch without modifying the current data."""
    csv_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so individual replacements are atomic.
    temporary = TemporaryDirectory(prefix=".refresh-", dir=csv_dir, delete=False)
    staging = Path(temporary.name)
    try:
        for task in tasks:
            if use_local_html:
                html = (debug_dir / task.html_filename).read_text(encoding="utf-8")
            else:
                html = DataFetcher.fetch_html(
                    task.url, COMMON_PARAMS | {"s[0][name]": task.sort_by}, cookies
                )
            HTMLParser.parse_to_csv(
                html,
                staging / task.csv_filename,
                debug_dir / task.html_filename
                if debug and not use_local_html
                else None,
                task.columns,
            )
        yield staging
    finally:
        if (csv_dir / CSV_REFRESH_MARKER).exists():
            logger.warning("Incomplete refresh; retaining staging files at %s", staging)
        else:
            temporary.cleanup()


def download_tasks() -> tuple[DownloadTable, ...]:
    """Return immutable table definitions independent of output directories."""
    return (
        DownloadTable(
            "analyses",
            URLS["analyses"],
            tuple(field_maps.REQUIRED_COLUMNS_ANALYSIS),
            "reference_code",
        ),
        DownloadTable(
            "papers",
            URLS["papers"],
            tuple(field_maps.REQUIRED_COLUMNS_PAPER),
            "reference_code",
        ),
        DownloadTable(
            "pubnotes",
            URLS["pubnotes"],
            tuple(field_maps.REQUIRED_COLUMNS_PUBNOTE),
            "final_ref_code",
        ),
        DownloadTable(
            "confnotes",
            URLS["confnotes"],
            tuple(field_maps.REQUIRED_COLUMNS_CONFNOTE),
            "final_ref_code",
        ),
    )


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
