# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Verified GLANCE HTTP transport, endpoints and certificate chain handling."""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests

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


class DataFetcher:
    @staticmethod
    def fetch_html(url, params, cookies):
        """Fetch HTML content from a URL."""
        try:
            logger.debug(f"Fetching data from {url} with params: {params}")
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
