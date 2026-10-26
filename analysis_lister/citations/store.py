# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""One persistent citation dictionary with provenance and protected entries."""

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import unquote, urlsplit

from analysis_lister.storage import atomic_write_text

DEFAULT_CACHE = Path("json/doi_metadata.json")
DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
MATERIALS = {"unknown", "publication", "erratum", "addendum", "editorial note"}


def normalize_doi(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a DOI string")
    value = value.strip()
    if value.lower().startswith(("https://", "http://")):
        url = urlsplit(value)
        if url.netloc.lower() not in {
            "doi.org",
            "www.doi.org",
            "dx.doi.org",
            "www.dx.doi.org",
        }:
            raise ValueError("Expected a bare DOI or doi.org URL")
        value = unquote(url.path.lstrip("/"))
    if value.lower().startswith("doi:"):
        value = value[4:].strip()
    if not DOI_PATTERN.fullmatch(value):
        raise ValueError("Expected a bare DOI or doi.org URL")
    return value.lower()


def citation_problem(entry):
    """Validate citation metadata loaded from the JSON store."""
    if isinstance(entry, str):
        return None if entry.strip() else "expected a nonempty string"
    if not isinstance(entry, dict):
        return "expected a nonempty string or citation record"
    required = {"citation", "source"}
    optional = {"material", "resolved_at", "source_url", "inspire_id"}
    if not required <= entry.keys() or entry.keys() - required - optional:
        return "citation record requires citation and source; unknown fields are not allowed"
    for key in ("citation", "source"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            return f"citation record {key} must be a nonempty string"
    if "material" in entry and (
        not isinstance(entry["material"], str) or entry["material"] not in MATERIALS
    ):
        return "citation record has invalid material"
    for key in optional - {"material"}:
        if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
            return f"citation record {key} must be a nonempty string"
    return None


def citation_record(value):
    problem = citation_problem(value)
    if problem:
        raise ValueError(problem)
    if isinstance(value, str):
        return {"citation": value, "source": "manual"}
    return value.copy()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in citation store")
        result[key] = value
    return result


def default_store_path():
    """Locate the single tracked store in a checkout or installed distribution."""
    checkout = Path(__file__).resolve().parents[2] / DEFAULT_CACHE
    if checkout.is_file():
        return checkout
    try:
        package = distribution("glance-analysis-lister")
        for path in package.files or []:
            if str(path).endswith("share/glance-analysis-lister/doi_metadata.json"):
                return Path(package.locate_file(path))
    except PackageNotFoundError:
        pass
    raise ValueError("The packaged citation dictionary is missing")


def load_store(path: Path):
    """Read exactly one dictionary, without merging another source into it."""
    if not path.exists():
        if path == DEFAULT_CACHE:
            path = default_store_path()
        else:
            return {}
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    if not isinstance(data, dict):
        raise ValueError("Citation store must be a DOI-keyed dictionary")
    result = {}
    for doi, value in data.items():
        key = normalize_doi(doi)
        if key in result:
            raise ValueError("Duplicate normalized DOI in citation store")
        entry = citation_record(value)
        if entry.get("material") == "unknown":
            entry.pop("material")
        result[key] = entry
    return result


def save_store(path: Path, records):
    normalized = {}
    for doi, value in records.items():
        key = normalize_doi(doi)
        if key in normalized:
            raise ValueError("Duplicate normalized DOI in citation store")
        entry = citation_record(value)
        if entry.get("material") == "unknown":
            entry.pop("material")
        normalized[key] = entry
    lines = [
        "  "
        + json.dumps(doi, ensure_ascii=False)
        + ": "
        + json.dumps(entry, ensure_ascii=False, sort_keys=True)
        for doi, entry in sorted(normalized.items())
    ]
    atomic_write_text(path, "{\n" + ",\n".join(lines) + ("\n" if lines else "") + "}\n")
