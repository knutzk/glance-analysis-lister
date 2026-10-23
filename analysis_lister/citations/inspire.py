# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Citation inspire: isolated concerns with no registry model dependency."""

import time
from contextlib import suppress
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from .formatting import format_journal_name, starting_page
from .store import normalize_doi

API = "https://inspirehep.net/api/doi/"


TIMEOUT = (10, 30)


PREFIXES = {
    "erratum": "Erratum: ",
    "addendum": "Addendum: ",
    "editorial note": "Editorial note: ",
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
    return f"{format_journal_name(journal)} {volume} ({year}) {starting_page(article)}"


def _material_assignments(doi_items, publications):
    """Combine explicit labels; infer only a unique remaining DOI/material pair."""
    labels = {}
    for item in doi_items:
        doi = normalize_doi(item.get("value", ""))
        values = labels.setdefault(doi, set())
        if "material" in item:
            material = item["material"]
            if not isinstance(material, str) or material not in {
                "publication",
                *PREFIXES,
            }:
                raise ValueError("Unsupported publication material")
            values.add(material)
    if any(len(values) > 1 for values in labels.values()):
        raise ValueError("Conflicting material labels for the requested DOI")
    assigned = {doi: next(iter(values)) for doi, values in labels.items() if values}
    unknown = set(labels) - set(assigned)
    materials = {item.get("material", "publication") for item in publications}
    remaining = materials - set(assigned.values())
    if len(unknown) == len(remaining) == 1:
        assigned[unknown.pop()] = remaining.pop()
    if set(assigned) != set(labels):
        raise ValueError("Ambiguous DOI-to-publication association")
    return assigned


def _merge_publications(candidates):
    """Merge compatible structured citations; never pick a conflicting first row."""
    merged = {}
    for item in candidates:
        fields = {}
        for name in ("journal_title", "journal_volume", "year", "page_end"):
            value = item.get(name)
            if value is not None and value != "":
                fields[name] = value.strip() if isinstance(value, str) else value
        journal = fields.get("journal_title")
        if journal is not None:
            if not isinstance(journal, str):
                raise ValueError("Invalid journal name")
            journal = format_journal_name(journal)
            fields["journal_title"] = journal
        # Where an explicit page range exists it is a valid citation locator,
        # even if the record also carries a publisher's internal article ID.
        locator = (
            item.get("page_start")
            if item.get("page_end") and item.get("page_start")
            else item.get("artid") or item.get("page_start")
        )
        if locator:
            if not isinstance(locator, str):
                raise ValueError("Invalid article/page identifier")
            fields["locator"] = locator.strip()
        for key, value in fields.items():
            if key in merged and merged[key] != value:
                raise ValueError("Conflicting publication metadata")
            merged[key] = value
    locator = merged.pop("locator", None)
    if "page_end" in merged:
        merged["page_start"] = locator
    else:
        merged["artid"] = locator
    return _format_publication(merged)


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
    publications = [item for item in publications if not item.get("hidden")]
    for item in publications:
        material = item.get("material", "publication")
        if not isinstance(material, str) or material not in {"publication", *PREFIXES}:
            raise ValueError("Unsupported publication material")
    assignments = _material_assignments(doi_items, publications)
    material = assignments[doi]
    same_material = {key for key, value in assignments.items() if value == material}
    candidates = [
        item
        for item in publications
        if not item.get("hidden") and item.get("material", "publication") == material
    ]
    if len(same_material) != 1 or not candidates:
        raise ValueError("Ambiguous DOI-to-publication association")
    citation = _merge_publications(candidates)
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
