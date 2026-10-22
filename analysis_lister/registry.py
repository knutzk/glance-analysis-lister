# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build a compact curated registry from saved API and HTML downloads."""

import copy
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from .api import RESOURCES, record_key, validate_registry as validate_api
from .csv_io import read_csv_rows
from .download import download_tasks
from .retrieval import SCOPE_FILENAME, RetrievalScope, check_scope, read_scope
from .storage import SUPPLEMENT_MANIFEST, atomic_write_text, require_complete_csv_batch

logger = logging.getLogger(__name__)
SCHEMA = "glance-curated-registry"
SUPPLEMENTS = {
    "analyses": {
        "Internal Note Editors": "internalNoteEditors",
    },
    "papers": {"Figures": "figuresUrl", "Current Paper Draft": "currentPaperDraft"},
    "pubnotes": {
        "Reference Code": "finalReferenceCode",
    },
}


def unique_names(values):
    """Keep source order and remove empty or repeated names."""
    if any(not isinstance(value, str) for value in values):
        raise ValueError("Names must be strings")
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def person_name(person):
    if not isinstance(person, dict):
        raise ValueError("Person must be an object")
    parts = [person.get(key) for key in ("firstName", "lastName")]
    if any(part is not None and not isinstance(part, str) for part in parts):
        raise ValueError("Person names must be strings")
    return " ".join(part.strip() for part in parts if part and part.strip())


def current_contact(person, as_of):
    if not isinstance(person, dict):
        raise ValueError("Team member must be an object")
    if not person.get("isAnalysisContact"):
        return False
    assignment = person.get("analysisContactAssignment") or {}
    start, end = assignment.get("startDate"), assignment.get("endDate")
    return (not start or date.fromisoformat(start) <= as_of) and (
        not end or date.fromisoformat(end) >= as_of
    )


def compact(value):
    """Consolidate named collections and replace other person objects by names."""
    if isinstance(value, list):
        return [compact(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "firstName" in value or "lastName" in value:
        return person_name(value)
    result = {}
    for key, item in value.items():
        if key == "keywords":
            if not isinstance(item, list):
                raise ValueError("Keywords must be a list")
            result[key] = unique_names(
                [
                    entry.get("name") if isinstance(entry, dict) else entry
                    for entry in item
                    if (entry.get("name") if isinstance(entry, dict) else entry)
                    is not None
                ]
            )
        elif key == "editorialBoard":
            board = item or []
            if not isinstance(board, list):
                raise ValueError("Editorial board must be a list")
            result[key] = unique_names([person_name(person) for person in board])
            result["editorialBoardChairs"] = unique_names(
                [person_name(person) for person in board if person.get("isChair")]
            )
            result["editorialBoardExOfficio"] = unique_names(
                [person_name(person) for person in board if person.get("isExOfficio")]
            )
        elif key == "readers":
            readers = item or []
            result[key] = unique_names([person_name(person) for person in readers])
            for flag, field in (
                ("isFirstReader", "firstReaders"),
                ("isSecondReader", "secondReaders"),
            ):
                result[field] = unique_names(
                    [person_name(person) for person in readers if person.get(flag)]
                )
        else:
            result[key] = compact(item)
    return result


def curate(api, supplements):
    """Preserve independent API identities; merge by native identifier only."""
    validate_api(api)
    as_of = datetime.fromisoformat(api["fetched_at"]).date()
    result = copy.deepcopy(api)
    result["schema"] = SCHEMA
    result["schema_version"] = 1
    statistics = {}
    for resource in RESOURCES:
        rows = supplements.get(resource, {})
        matched = conflicts = 0
        records = []
        for record in result[resource]:
            team = record.pop("analysisTeam", []) or []
            if not isinstance(team, list):
                raise ValueError("Analysis team must be a list")
            record["analysisContacts"] = unique_names(
                [
                    person_name(person)
                    for person in team
                    if current_contact(person, as_of)
                ]
            )
            record["contactEditors"] = unique_names(
                [
                    person_name(person)
                    for person in team
                    if person.get("isContactEditor")
                ]
            )
            row = rows.get(record_key(record, resource))
            if row is not None:
                matched += 1
                for column, field in SUPPLEMENTS.get(resource, {}).items():
                    value = row[column].strip()
                    if not value:
                        continue
                    if field == "internalNoteEditors":
                        value = unique_names(value.split(","))
                    if record.get(field) not in (None, "", []):
                        if record[field] != value:
                            conflicts += 1
                        continue
                    record[field] = value
            records.append(compact(record))
        result[resource] = sorted(
            records, key=lambda record: record_key(record, resource)
        )
        if resource in SUPPLEMENTS:
            statistics[resource] = {
                "matched": matched,
                "api_without_supplement": len(records) - matched,
                "supplement_without_api": len(rows) - matched,
                "conflicting_fields_api_retained": conflicts,
            }
    result["curation"] = {
        "built_at": datetime.now(UTC).isoformat(),
        "contacts_as_of": as_of.isoformat(),
        "api_schema": api["schema"],
        "supplement_fields": SUPPLEMENTS,
        "supplement_statistics": statistics,
    }
    return result


def validate_registry(data):
    """Validate the curated container independently of legacy view models."""
    if (
        not isinstance(data, dict)
        or data.get("schema") != SCHEMA
        or data.get("schema_version") != 1
        or not isinstance(data.get("counts"), dict)
    ):
        raise ValueError("Destination is not a supported curated registry")
    for resource in RESOURCES:
        records = data.get(resource)
        if not isinstance(records, list) or not records:
            raise ValueError(f"{resource}: missing or empty records")
        keys = [record_key(record, resource) for record in records]
        if len(keys) != len(set(keys)) or data["counts"].get(resource) != len(keys):
            raise ValueError(f"{resource}: inconsistent counts or identifiers")
        for record in records:
            if "analysisTeam" in record:
                raise ValueError("Curated registry must not contain analysisTeam")
            for field in ("analysisContacts", "contactEditors"):
                if not isinstance(record.get(field), list) or any(
                    not isinstance(name, str) for name in record[field]
                ):
                    raise ValueError(f"{resource}: invalid curated people list")


def read_supplements(directory):
    """Require a complete, identifiable supplemental batch with scope metadata."""
    require_complete_csv_batch(directory)
    manifest = json.loads((directory / SUPPLEMENT_MANIFEST).read_text(encoding="utf-8"))
    tasks = download_tasks()
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "glance-csv-supplements"
        or manifest.get("schema_version") != 1
        or manifest.get("tables") != {task.name: list(task.columns) for task in tasks}
    ):
        raise ValueError("Unsupported supplemental CSV schema")
    scope = read_scope(directory)
    if scope is None:
        raise ValueError("Supplemental CSVs require retrieval scope metadata")
    result = {}
    for task in tasks:
        rows = read_csv_rows(
            directory / task.csv_filename,
            task.columns,
            key=task.key,
            prefix=task.prefix,
        )
        result[task.name] = {row[task.key]: row for row in rows}
    require_complete_csv_batch(directory)
    return result, {"manifest": manifest, "retrieval_scope": scope.metadata()}


def build_registry(api_path, csv_dir, output, *, allow_count_drop=False):
    """Build offline and atomically publish without overwriting source inputs."""
    api_path, csv_dir, output = Path(api_path), Path(csv_dir), Path(output)
    inputs = [api_path, csv_dir / SUPPLEMENT_MANIFEST, csv_dir / SCOPE_FILENAME]
    inputs.extend(csv_dir / task.csv_filename for task in download_tasks())
    if any(output.resolve() == path.resolve() for path in inputs):
        raise ValueError("Registry output must not overwrite an input")
    api = json.loads(api_path.read_text(encoding="utf-8"))
    supplements, provenance = read_supplements(csv_dir)
    candidate = curate(api, supplements)
    candidate["curation"]["html_source"] = provenance
    validate_registry(candidate)
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        validate_registry(previous)
        previous_scope = (
            previous.get("curation", {}).get("html_source", {}).get("retrieval_scope")
        )
        check_scope(
            RetrievalScope.from_dict(provenance["retrieval_scope"]),
            RetrievalScope.from_dict(previous_scope)
            if previous_scope is not None
            else None,
        )
        if previous.get("source", {}).get("base_url") != candidate["source"].get(
            "base_url"
        ):
            raise ValueError("API endpoint differs; choose a new output")
        for resource in RESOURCES:
            if (
                not allow_count_drop
                and candidate["counts"][resource] < previous["counts"][resource] * 0.8
            ):
                raise ValueError(f"{resource}: count dropped by more than 20%")
    atomic_write_text(
        output, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    )
    for resource, counts in candidate["curation"]["supplement_statistics"].items():
        logger.info("HTML supplement %s: %s", resource, counts)
    return candidate["counts"]
