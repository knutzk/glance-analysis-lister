# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline public identifiers and canonical paper URLs, with explicit evidence."""

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import unquote, urlsplit

PUB_PATTERN = r"ATL-[A-Z]+-PUB-\d{4}-\d+"


def default_identifiers_path():
    source = Path(__file__).resolve().parents[2] / "json/pubnote_identifiers.json"
    if source.is_file():
        return source
    try:
        package = distribution("glance-analysis-lister")
        for path in package.files or []:
            if str(path).endswith(
                "share/glance-analysis-lister/pubnote_identifiers.json"
            ):
                return Path(package.locate_file(path))
    except PackageNotFoundError:
        pass
    raise ValueError("The packaged PUB-note identifier dictionary is missing")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in public identifier dictionary")
        result[key] = value
    return result


def load_identifiers(path=None):
    data = json.loads(
        (Path(path) if path is not None else default_identifiers_path()).read_text(),
        object_pairs_hook=_unique_pairs,
    )
    if not isinstance(data, dict):
        raise ValueError("PUB-note identifiers must be a CDS-record-keyed dictionary")
    for key, value in data.items():
        if (
            not re.fullmatch(r"[1-9]\d*", key)
            or not isinstance(value, dict)
            or set(value) != {"identifier", "source_url"}
            or not isinstance(value.get("identifier"), str)
            or not re.fullmatch(PUB_PATTERN, value["identifier"])
            or value["source_url"] != f"https://cds.cern.ch/record/{key}"
        ):
            raise ValueError("Invalid public PUB-note identifier mapping")
    return data


def cds_record_id(url):
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or parts.hostname not in {
        "cds.cern.ch",
        "cdsweb.cern.ch",
    }:
        return None
    match = re.fullmatch(r"/record/([1-9]\d*)/?", parts.path)
    return match.group(1) if match else None


def final_identifier(record, resource):
    pattern = r"ATLAS-CONF-\d{4}-\d+" if resource == "confnotes" else PUB_PATTERN
    for key in ("finalReferenceCode", "gal_finalReferenceCode"):
        value = record.get(key)
        if isinstance(value, str) and re.fullmatch(pattern, value):
            return value
    return None


def enrich_public_identifiers(record, resource, identifiers):
    """Return a provenance entry; never guess a PUB number or make a request."""
    if resource == "papers":
        phase = record.get("publicationPhase") or {}
        published = (
            record.get("status") == "Publication Phase Finished"
            or phase.get("publishedOnlineDate")
            or phase.get("arXivSubmissionDate")
        )
        reference = record.get("referenceCode", "")
        if published and re.fullmatch(r"[A-Z]+-\d{4}-\d{2}", reference):
            record["gal_figuresUrl"] = (
                f"https://atlas.web.cern.ch/Atlas/GROUPS/PHYSICS/PAPERS/{reference}/"
            )
            return {
                "field": "gal_figuresUrl",
                "source": "canonical-paper-url",
                "availability_checked": False,
            }
        return None
    if resource not in {"confnotes", "pubnotes"}:
        return None
    native = final_identifier(record, resource)
    if native:
        return (
            {"field": "finalReferenceCode", "source": "api"}
            if record.get("finalReferenceCode") == native
            else {"field": "gal_finalReferenceCode", "source": "provided-enrichment"}
        )
    phase = record.get("phase1") or {}
    url = phase.get("publicWebPageUrlForFiguresAndTables") or ""
    pattern = r"ATLAS-CONF-\d{4}-\d+" if resource == "confnotes" else PUB_PATTERN
    matches = set(
        re.findall(r"(?<![A-Za-z0-9-])" + pattern + r"(?![A-Za-z0-9-])", unquote(url))
    )
    if len(matches) == 1:
        record["gal_finalReferenceCode"] = matches.pop()
        return {
            "field": "gal_finalReferenceCode",
            "source": "api-public-url",
            "source_url": url,
        }
    if not matches and resource == "pubnotes":
        for field in ("publicWebPageUrlForFiguresAndTables", "draftCdsUrl"):
            cds_id = cds_record_id(phase.get(field))
            if cds_id in identifiers:
                entry = identifiers[cds_id]
                record["gal_finalReferenceCode"] = entry["identifier"]
                return {
                    "field": "gal_finalReferenceCode",
                    "source": "bundled-cds-identifier",
                    "api_field": "phase1." + field,
                    "cds_record": cds_id,
                    "source_url": entry["source_url"],
                }
    if record.get("status") not in {"Created", "Closed"} and (
        record.get("status") == "Phase 1 Finished" or phase.get("releaseDate")
    ):
        return {
            "field": "gal_finalReferenceCode",
            "source": "unresolved",
            "reason": "note has release evidence but no unambiguous public identifier in the API or bundled dictionary",
        }
    return None
