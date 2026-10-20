# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Incremental DOI inference and explicit, bounded INSPIRE metadata retrieval."""

import json
import logging
import re
import time
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import requests

from analysis_lister.citation_store import effective_store, normalize_doi, save_store
from analysis_lister.lookup_dicts.reporting import lookup_notice, lookup_report

logger = logging.getLogger(__name__)
API = "https://inspirehep.net/api/doi/"
TIMEOUT = (10, 30)
JHEP = re.compile(r"10\.1007/jhep(0[1-9]|1[0-2])\((\d{4})\)(\d{3,})", re.I)
PREFIXES = {
    "erratum": "Erratum: ",
    "addendum": "Addendum: ",
    "editorial note": "Editorial note: ",
}


def infer_citation(doi):
    """Infer only a fully specified JHEP citation; material remains unknown."""
    match = JHEP.fullmatch(normalize_doi(doi))
    if match is None:
        return None
    month, year, article = match.groups()
    return {
        "citation": f"JHEP {month} ({year}) {article}",
        "source": "doi-pattern:jhep",
    }


def _format_publication(info):
    journal = info.get("journal_title")
    volume = info.get("journal_volume")
    year = info.get("year")
    article = info.get("artid") or info.get("page_start")
    if not all(isinstance(v, str) and v.strip() for v in (journal, volume, article)):
        raise ValueError("Incomplete journal citation")
    if type(year) is not int or not 1000 <= year <= 9999:
        raise ValueError("Missing or invalid publication year")
    if not info.get("artid") and info.get("page_end"):
        article += f"–{info['page_end']}"
    return f"{journal} {volume} ({year}) {article}"


def inspire_citation(doi, payload):
    """Require an explicit, unambiguous DOI/material-to-publication association."""
    doi = normalize_doi(doi)
    if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict):
        raise ValueError("Invalid INSPIRE metadata response")
    metadata = payload["metadata"]
    doi_items = metadata.get("dois", [])
    publications = metadata.get("publication_info", [])
    if not isinstance(doi_items, list) or not isinstance(publications, list):
        raise ValueError("Invalid INSPIRE DOI/publication lists")
    if any(not isinstance(item, dict) for item in doi_items + publications):
        raise ValueError("Invalid INSPIRE DOI/publication entries")
    matches = [
        item for item in doi_items if normalize_doi(item.get("value", "")) == doi
    ]
    if not matches:
        raise ValueError("INSPIRE did not return the requested DOI")
    material = matches[0].get("material", "publication")
    if not isinstance(material, str) or material not in {"publication", *PREFIXES}:
        raise ValueError("Unsupported publication material")
    # INSPIRE may repeat the same DOI for publisher and arXiv sources.
    # Accept consistent repetitions, but never conflicting material labels.
    if any(item.get("material", "publication") != material for item in matches):
        raise ValueError("Conflicting material labels for the requested DOI")
    same_material = {
        normalize_doi(item["value"])
        for item in doi_items
        if item.get("material", "publication") == material
    }
    candidates = [
        item
        for item in publications
        if not item.get("hidden") and item.get("material", "publication") == material
    ]
    if len(same_material) != 1 or len(candidates) != 1:
        raise ValueError("Ambiguous DOI-to-publication association")
    citation = _format_publication(candidates[0])
    return {
        "citation": PREFIXES.get(material, "") + citation,
        "source": "inspire",
        "material": material,
        "source_url": API + quote(doi, safe="/"),
        **(
            {"inspire_id": str(metadata["control_number"])}
            if metadata.get("control_number")
            else {}
        ),
    }


class InspireClient:
    """Separate public session; never reuse GLANCE cookies or credentials."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "glance-analysis-lister/0.1 DOI resolver"}
        )
        self.last_request = None

    def close(self):
        self.session.close()

    def fetch(self, doi):
        url = API + quote(normalize_doi(doi), safe="/")
        for attempt in range(3):
            if self.last_request is not None:
                time.sleep(max(0, 0.4 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, timeout=TIMEOUT, verify=True)
            except requests.exceptions.SSLError:
                raise
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
                continue
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                delay = 5 if response.status_code == 429 else 2**attempt
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        with suppress(ValueError, TypeError, OverflowError):
                            delay = max(
                                delay,
                                (
                                    parsedate_to_datetime(retry_after)
                                    - datetime.now(UTC)
                                ).total_seconds(),
                            )
                if delay > 60:
                    raise ValueError(
                        "INSPIRE requests a longer pause; retry this DOI later"
                    )
                time.sleep(delay)
                continue
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        raise ValueError("INSPIRE retry limit reached")


def snapshot_dois(path: Path):
    """Read DOI inputs only, without reconstructing private analysis records."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
        raise ValueError("Snapshot requires an entries dictionary")
    result = set()
    malformed = 0
    for entry in data["entries"].values():
        if not isinstance(entry, dict):
            raise ValueError("Invalid snapshot entry")
        # The raw URLs are authoritative; serialized derived DOIs can be stale.
        values = entry.get("doi_urls", entry.get("dois", []))
        if not isinstance(values, list):
            raise ValueError("Snapshot DOI fields must be lists")
        for doi in values:
            if not doi:
                continue
            try:
                result.add(normalize_doi(doi))
            except ValueError:
                malformed += 1
    if malformed:
        lookup_notice(
            logger,
            logging.WARNING,
            "Skipped %d malformed DOI values in snapshot; valid DOIs will still be processed",
            malformed,
        )
    return result


@lookup_report()
def resolve_dois(dois, cache_path: Path, *, method="infer", refresh=False, limit=None):
    """Resolve missing entries; atomically checkpoint each success, never failures."""
    if method not in {"infer", "inspire", "auto"}:
        raise ValueError("Unknown DOI resolution method")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Resolution limit must be positive")
    inputs = sorted({normalize_doi(doi) for doi in dois})
    records = effective_store(cache_path)
    summary = Counter(
        resolved=0, existing=0, locked=0, unresolved=0, failed=0, deferred=0
    )
    client = None
    attempted = 0
    try:
        for doi in inputs:
            previous = records.get(doi)
            if previous is not None:
                if previous["source"] == "manual":
                    summary["locked"] += 1
                    continue
                if not refresh:
                    summary["existing"] += 1
                    continue
            if limit is not None and attempted >= limit:
                summary["deferred"] += 1
                continue
            attempted += 1
            try:
                record = infer_citation(doi) if method in {"infer", "auto"} else None
                if record is None and method in {"inspire", "auto"}:
                    if client is None:
                        client = InspireClient()
                    payload = client.fetch(doi)
                    record = (
                        inspire_citation(doi, payload) if payload is not None else None
                    )
                if record is None:
                    summary["unresolved"] += 1
                    lookup_notice(
                        logger,
                        logging.WARNING,
                        "%s: no citation resolved; entry remains retryable",
                        doi,
                    )
                    continue
            except requests.RequestException:
                summary["failed"] += 1
                lookup_notice(
                    logger,
                    logging.WARNING,
                    "%s: INSPIRE request failed; entry remains retryable",
                    doi,
                )
                continue
            except ValueError as error:
                summary["unresolved"] += 1
                lookup_notice(
                    logger,
                    logging.WARNING,
                    "%s: %s; entry remains retryable",
                    doi,
                    error,
                )
                continue
            record["resolved_at"] = datetime.now(UTC).isoformat()
            if (
                previous is not None
                and previous.get("material", "unknown") != "unknown"
                and record.get("material", "unknown") == "unknown"
            ):
                summary["existing"] += 1
                continue
            records[doi] = record
            save_store(cache_path, records)
            summary["resolved"] += 1
        save_store(cache_path, records)
    finally:
        if client is not None:
            client.close()
    return dict(summary)
