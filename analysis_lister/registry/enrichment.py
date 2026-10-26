# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Curate saved API records, retaining sources until the final removal pass."""

import copy
import json
import logging
from datetime import UTC, date, datetime
from hashlib import sha256

from .public_identifiers import enrich_public_identifiers, load_identifiers
from .publication_dois import enrich_paper
from .schema import (
    PREFIX,
    RESOURCES,
    SCHEMA,
    SCHEMA_VERSION,
    record_key,
    validate_api_registry as validate_api,
)

logger = logging.getLogger(__name__)
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


def curate(api, *, citations=None, pubnote_identifiers=None):
    """Curate independent API records using offline identifier/citation data."""
    validate_api(api)
    identifiers = (
        load_identifiers() if pubnote_identifiers is None else pubnote_identifiers
    )
    identifier_statistics = {}
    reject_reserved_keys(api)
    as_of = datetime.fromisoformat(api["fetched_at"]).date()
    result = copy.deepcopy(api)
    result["schema"] = SCHEMA
    result["schema_version"] = SCHEMA_VERSION
    citations = citations if citations is not None else {}
    doi_stats = {
        "papers_with_dois": 0,
        "resolved": 0,
        "unresolved": 0,
        "malformed_links": 0,
    }
    for resource in RESOURCES:
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
            evidence = enrich_public_identifiers(record, resource, identifiers)
            if evidence:
                record["gal_publicationProvenance"] = evidence
                source = evidence["source"]
                stats = identifier_statistics.setdefault(resource, {})
                stats[source] = stats.get(source, 0) + 1
                if source == "unresolved":
                    logger.warning(
                        "Public identifier unresolved for %s: %s",
                        record_key(record, resource),
                        evidence["reason"],
                    )
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
    result["gal_curation"] = {
        "built_at": datetime.now(UTC).isoformat(),
        "public_identifier_statistics": identifier_statistics,
        "pubnote_identifier_store": {
            "entries": len(identifiers),
            "sha256": sha256(
                json.dumps(identifiers, sort_keys=True).encode()
            ).hexdigest(),
        },
        "contacts_as_of": as_of.isoformat(),
        "api_schema": api["schema"],
        "removed_keys": list(REMOVED_KEYS),
        "doi_statistics": doi_stats,
        "citation_store": {
            "entries": len(citations),
            "sha256": sha256(
                json.dumps(citations, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        },
    }
    return result
