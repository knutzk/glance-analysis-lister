# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Authenticated GLANCE downloads and staged HTML-to-CSV conversion."""

import csv
import json
import logging
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import requests
from attrs import field, frozen

from analysis_lister.glance import field_maps
from analysis_lister.html_tables import (
    parse_html_table,
    table_to_rows,
    validate_table_completeness,
)
from analysis_lister.retrieval import (
    SCOPE_FILENAME,
    RetrievalScope,
    check_scope,
    load_scope,
    read_scope,
)
from analysis_lister.storage import CSV_REFRESH_MARKER

logger = logging.getLogger(__name__)

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
    def parse_to_csv(
        html: str,
        output_csv: Path,
        debug_path: Path | None = None,
        column_filter: Sequence[str] | None = None,
    ) -> None:
        """Save diagnostic HTML, then validate and write a complete CSV table."""
        source = str(output_csv)
        logger.info("Parsing HTML content to extract table data for %s", source)
        table = parse_html_table(html, source=source)
        # Keep diagnostic HTML even if header or row validation subsequently fails.
        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(
                html + ("" if html.endswith("\n") else "\n"), encoding="utf-8"
            )
            logger.debug(
                "Full response including result counters saved to %s", debug_path
            )

        csv_data = table_to_rows(table, source=source, column_filter=column_filter)
        validate_table_completeness(table, len(csv_data) - 1, source=source)
        with output_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)
        logger.info("CSV file successfully generated: %s", output_csv)


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
    scope: RetrievalScope | None = None,
) -> Iterator[Path]:
    """Yield a complete CSV batch without modifying the current data."""
    scope = scope or load_scope()
    if any(csv_dir.glob("*.csv")) or (csv_dir / SCOPE_FILENAME).exists():
        check_scope(scope, read_scope(csv_dir))
    if use_local_html:
        check_scope(scope, read_scope(debug_dir))
    csv_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so individual replacements are atomic.
    temporary = TemporaryDirectory(prefix=".refresh-", dir=csv_dir, delete=False)
    staging = Path(temporary.name)
    try:
        if debug and not use_local_html:
            (debug_dir / SCOPE_FILENAME).unlink(missing_ok=True)
        for task in tasks:
            if use_local_html:
                html = (debug_dir / task.html_filename).read_text(encoding="utf-8")
            else:
                html = DataFetcher.fetch_html(
                    task.url,
                    COMMON_PARAMS | scope.query_params() | {"s[0][name]": task.sort_by},
                    cookies,
                )
            HTMLParser.parse_to_csv(
                html,
                staging / task.csv_filename,
                debug_dir / task.html_filename
                if debug and not use_local_html
                else None,
                task.columns,
            )
        metadata = json.dumps(scope.metadata(), indent=2) + "\n"
        (staging / SCOPE_FILENAME).write_text(metadata, encoding="utf-8")
        if debug and not use_local_html:
            (debug_dir / SCOPE_FILENAME).write_text(metadata, encoding="utf-8")
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
