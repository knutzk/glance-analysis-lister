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

from analysis_lister.citation_store import (
    load_store,
    normalize_doi,
    save_store,
)
from analysis_lister.diagnostics import lookup_notice, lookup_report

logger = logging.getLogger(__name__)
API = "https://inspirehep.net/api/doi/"
TIMEOUT = (10, 30)
JHEP = re.compile(r"10\.1007/jhep(0[1-9]|1[0-2])\((\d{4})\)(\d{3,})", re.I)
PREFIXES = {
    "erratum": "Erratum: ",
    "addendum": "Addendum: ",
    "editorial note": "Editorial note: ",
}
# Presentation spellings follow the existing manual citations. Explicit aliases
# also reconcile INSPIRE's Rept. abbreviations with the project's Rep. style.
JOURNAL_NAMES = {
    "phys.lett.b": "Phys. Lett. B",
    "phys.rev.c": "Phys. Rev. C",
    "phys.rev.d": "Phys. Rev. D",
    "phys.rev.lett.": "Phys. Rev. Lett.",
    "phys.rept.": "Phys. Rep.",
    "phys.rep.": "Phys. Rep.",
    "rept.prog.phys.": "Rep. Prog. Phys.",
    "rep.prog.phys.": "Rep. Prog. Phys.",
    "eur.phys.j.c": "Eur. Phys. J. C",
    "comput.softw.bigsci.": "Comput. Softw. Big Sci.",
    "sci.bull.": "Sci. Bull.",
    "newj.phys.": "New J. Phys.",
    "chin.phys.c": "Chin. Phys. C",
    "naturephys.": "Nature Phys.",
    "naturecommun.": "Nature Commun.",
    "eur.phys.j.plus": "Eur. Phys. J. Plus",
    "mach.learn.sci.tech.": "Mach. Learn. Sci. Tech.",
}


def format_journal_name(journal):
    """Normalise known abbreviations without guessing punctuation for others."""
    key = re.sub(r"\s+", "", journal).casefold()
    return JOURNAL_NAMES.get(key, " ".join(journal.split()))


def starting_page(locator):
    """Shorten conventional numeric or letter-prefixed page ranges."""
    match = re.fullmatch(
        r"(?P<prefix>[A-Za-z]*)(?P<start>\d+)\s*[-–—]\s*"
        r"(?P<end_prefix>[A-Za-z]*)(?P<end>\d+)",
        locator,
    )
    if (
        match
        and match["end_prefix"] in ("", match["prefix"])
        and int(match["end"]) >= int(match["start"])
    ):
        return match["prefix"] + match["start"]
    return locator


def format_citations(path: Path):
    """Apply journal typography offline, retaining manual entries and provenance."""
    entries = load_store(path)
    changed = 0
    pattern = re.compile(
        r"(?P<prefix>(?:Erratum|Addendum|Editorial note): )?"
        r"(?P<journal>.+?) (?P<volume>\S+) \((?P<year>\d{4})\) (?P<locator>.+)",
    )
    for entry in entries.values():
        if entry["source"] == "manual":
            continue
        match = pattern.fullmatch(entry["citation"])
        if match is None:
            continue
        citation = (
            (match["prefix"] or "")
            + format_journal_name(match["journal"])
            + f" {match['volume']} ({match['year']}) "
            + starting_page(match["locator"])
        )
        if citation != entry["citation"]:
            entry["citation"] = citation
            changed += 1
    if changed:
        save_store(path, entries)
    return changed


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
    records = load_store(cache_path)
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
