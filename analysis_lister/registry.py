# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build a compact curated registry from saved API and HTML downloads."""

import copy
import json
import logging
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

from .api import RESOURCES, record_key, validate_registry as validate_api
from .citation_store import DEFAULT_CACHE, load_store
from .csv_io import read_csv_rows
from .download import download_tasks
from .publication_dois import enrich_paper
from .retrieval import SCOPE_FILENAME, RetrievalScope, check_scope, read_scope
from .storage import SUPPLEMENT_MANIFEST, atomic_write_text, require_complete_csv_batch

logger = logging.getLogger(__name__)
SCHEMA = "glance-curated-registry"
PREFIX = "gal_"
# Removed recursively only after all enrichments have been computed.
REMOVED_KEYS = [
    "analysisTeam",
    "keywords",
    "triggers",
    "statisticalTools",
    "repositories",
    "groups",
    "eoiMeetings",
    "editorialBoardRequestMeetings",
    "preApprovalMeetings",
    "approvalMeetings",
    "editorialBoard",
    "readers",
    "signOffResponsible",
    "firstSignOffResponsible",
    "secondSignOffResponsible",
    "pubcommChairOrDeputyOrDelegated",
    "spokespersonOrDeputyOrDelegated",
]
# Source collection -> dictionary field to extract into gal_<collection>.
STRING_LIST_FIELDS = {
    "keywords": "name",
    "triggers": "name",
    "statisticalTools": "name",
}
MEETING_DATE_FIELDS = {
    "eoiMeetings": "gal_eoiMeetingDates",
    "editorialBoardRequestMeetings": "gal_editorialBoardRequestMeetingDates",
    "preApprovalMeetings": "gal_preApprovalMeetingDates",
    "approvalMeetings": "gal_approvalMeetingDates",
}
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


def string_list(values, value_key="name", *, label="Values"):
    """Extract strings from records or strings, preserving order and deduplicating."""
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    extracted = [
        entry.get(value_key) if isinstance(entry, dict) else entry for entry in values
    ]
    return unique_names([value for value in extracted if value is not None])


def meeting_dates(meetings):
    """Extract ISO calendar dates in source order without timezone conversion."""
    if not isinstance(meetings, list):
        raise ValueError("Meetings must be a list")
    result = []
    for meeting in meetings:
        if not isinstance(meeting, dict):
            raise ValueError("Meeting must be an object")
        value = meeting.get("date")
        if value in (None, ""):
            continue
        if not isinstance(value, str):
            raise ValueError("Meeting date must be an ISO date or datetime string")
        try:
            result.append(datetime.fromisoformat(value.strip()).date().isoformat())
        except ValueError as error:
            raise ValueError(
                "Meeting date must be an ISO date or datetime string"
            ) from error
    return result


def compact_groups(groups, *, reference):
    """Flatten group names, warning when a leading assignment is not singular."""
    if not isinstance(groups, dict):
        raise ValueError("Groups must be an object")
    result = copy.deepcopy(groups)
    for key in ("leadingGroup", "leadingSubgroup"):
        value = groups.get(key)
        entries = (
            value if isinstance(value, list) else ([] if value is None else [value])
        )
        names = string_list(entries, label=key)
        if value is not None and (len(entries) != 1 or len(names) != 1):
            logger.warning(
                "%s: groups.%s expected one named assignment; found %d entries "
                "and %d distinct names; using the first name or null",
                reference,
                key,
                len(entries),
                len(names),
            )
        result[key] = names[0] if names else None
    for key in ("subgroups", "otherGroups"):
        result[key] = string_list(groups.get(key) or [], label=key)
    return result


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


def reject_reserved_keys(value):
    """Fail explicitly if a future API field would collide with our namespace."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.startswith(PREFIX):
                raise ValueError("API input uses reserved gal_ namespace")
            reject_reserved_keys(item)
    elif isinstance(value, list):
        for item in value:
            reject_reserved_keys(item)


def compact(value, *, reference="Unknown record"):
    """Add curated fields while retaining every original source field."""
    if isinstance(value, list):
        return [compact(item, reference=reference) for item in value]
    if not isinstance(value, dict):
        return value
    result = copy.deepcopy(value)
    for key, item in value.items():
        if key == "analysisTeam":
            continue  # Contacts and editors are derived separately in curate().
        if key in STRING_LIST_FIELDS:
            result[PREFIX + key] = string_list(item, STRING_LIST_FIELDS[key], label=key)
        elif key in MEETING_DATE_FIELDS:
            result[MEETING_DATE_FIELDS[key]] = meeting_dates(item)
        elif key == "groups":
            result[PREFIX + key] = compact_groups(item, reference=reference)
        elif key == "editorialBoard":
            board = item or []
            if not isinstance(board, list):
                raise ValueError("Editorial board must be a list")
            result[PREFIX + key] = unique_names(
                [person_name(person) for person in board]
            )
            result["gal_editorialBoardChairs"] = unique_names(
                [person_name(person) for person in board if person.get("isChair")]
            )
            result["gal_editorialBoardExOfficio"] = unique_names(
                [person_name(person) for person in board if person.get("isExOfficio")]
            )
        elif key == "readers":
            readers = item or []
            result[PREFIX + key] = unique_names(
                [person_name(person) for person in readers]
            )
            for flag, field in (
                ("isFirstReader", "gal_firstReaders"),
                ("isSecondReader", "gal_secondReaders"),
            ):
                result[field] = unique_names(
                    [person_name(person) for person in readers if person.get(flag)]
                )
        else:

            def is_person(value):
                return isinstance(value, dict) and (
                    "firstName" in value or "lastName" in value
                )

            renamed = is_person(item) or (
                isinstance(item, list) and any(is_person(entry) for entry in item)
            )
            if renamed:
                result[PREFIX + key] = (
                    [
                        person_name(entry)
                        if is_person(entry)
                        else compact(entry, reference=reference)
                        for entry in item
                    ]
                    if isinstance(item, list)
                    else person_name(item)
                )
            else:
                result[key] = compact(item, reference=reference)
    return result


def remove_keys(value, keys):
    """Remove configured source keys without depending on enrichment rules."""
    if isinstance(value, list):
        return [remove_keys(item, keys) for item in value]
    if isinstance(value, dict):
        return {
            key: remove_keys(item, keys)
            for key, item in value.items()
            if key not in keys
        }
    return value


def curate(api, supplements, *, citations=None):
    """Preserve independent API identities; merge by native identifier only."""
    validate_api(api)
    reject_reserved_keys(api)
    as_of = datetime.fromisoformat(api["fetched_at"]).date()
    result = copy.deepcopy(api)
    result["schema"] = SCHEMA
    result["schema_version"] = 2
    statistics = {}
    citations = citations if citations is not None else {}
    doi_stats = {
        "papers_with_dois": 0,
        "resolved": 0,
        "unresolved": 0,
        "malformed_links": 0,
    }
    for resource in RESOURCES:
        rows = supplements.get(resource, {})
        matched = conflicts = 0
        records = []
        for record in result[resource]:
            team = record.get("analysisTeam", []) or []
            if not isinstance(team, list):
                raise ValueError("Analysis team must be a list")
            record["gal_analysisContacts"] = unique_names(
                [
                    person_name(person)
                    for person in team
                    if current_contact(person, as_of)
                ]
            )
            record["gal_contactEditors"] = unique_names(
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
                    record[PREFIX + field] = value
            if resource == "papers":
                entries, malformed = enrich_paper(record, citations)
                doi_stats["papers_with_dois"] += bool(entries)
                doi_stats["resolved"] += sum(entry["resolved"] for entry in entries)
                doi_stats["unresolved"] += sum(
                    not entry["resolved"] for entry in entries
                )
                doi_stats["malformed_links"] += malformed
            enriched = compact(record, reference=record_key(record, resource))
            records.append(remove_keys(enriched, REMOVED_KEYS))
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
    result["gal_curation"] = {
        "built_at": datetime.now(UTC).isoformat(),
        "contacts_as_of": as_of.isoformat(),
        "api_schema": api["schema"],
        "supplement_fields": {
            resource: {column: PREFIX + field for column, field in fields.items()}
            for resource, fields in SUPPLEMENTS.items()
        },
        "removed_keys": list(REMOVED_KEYS),
        "supplement_statistics": statistics,
        "doi_statistics": doi_stats,
        "citation_store": {
            "entries": len(citations),
            "sha256": sha256(
                json.dumps(citations, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        },
    }
    return result


def validate_registry(data):
    """Validate the curated container independently of legacy view models."""
    if (
        not isinstance(data, dict)
        or data.get("schema") != SCHEMA
        or data.get("schema_version") not in (1, 2)
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
            for name in ("analysisContacts", "contactEditors"):
                field = PREFIX + name if data["schema_version"] == 2 else name
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


def build_registry(
    api_path, csv_dir, output, *, allow_count_drop=False, doi_cache=DEFAULT_CACHE
):
    """Build offline and atomically publish without overwriting source inputs."""
    api_path, csv_dir, output = Path(api_path), Path(csv_dir), Path(output)
    inputs = [api_path, csv_dir / SUPPLEMENT_MANIFEST, csv_dir / SCOPE_FILENAME]
    inputs.append(Path(doi_cache))
    inputs.extend(csv_dir / task.csv_filename for task in download_tasks())
    if any(output.resolve() == path.resolve() for path in inputs):
        raise ValueError("Registry output must not overwrite an input")
    api = json.loads(api_path.read_text(encoding="utf-8"))
    supplements, provenance = read_supplements(csv_dir)
    candidate = curate(api, supplements, citations=load_store(Path(doi_cache)))
    candidate["gal_curation"]["html_source"] = provenance
    validate_registry(candidate)
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        validate_registry(previous)
        previous_scope = (
            previous.get("gal_curation", previous.get("curation", {}))
            .get("html_source", {})
            .get("retrieval_scope")
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
    for resource, counts in candidate["gal_curation"]["supplement_statistics"].items():
        logger.info("HTML supplement %s: %s", resource, counts)
    return candidate["counts"]
