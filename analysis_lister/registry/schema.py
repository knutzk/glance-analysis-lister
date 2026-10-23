# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Resource identities and curated-format validation, without I/O or models."""

API_SCHEMA = "glance-api-registry"
SCHEMA = "glance-curated-registry"
SCHEMA_VERSION = 2
PREFIX = "gal_"
RESOURCES = ("analyses", "papers", "confnotes", "pubnotes")


def record_key(record, resource):
    """Use the native identifier, including note and analysis prefixes."""
    if not isinstance(record, dict):
        raise ValueError(f"{resource}: record must be an object")
    field = (
        "temporaryReferenceCode"
        if resource in {"confnotes", "pubnotes"}
        else "referenceCode"
    )
    key = record.get(field)
    if not isinstance(key, str) or not key:
        raise ValueError(f"{resource}: missing {field}")
    return key


def validate_registry(data):
    """Validate the curated container independently of legacy view models."""
    if (
        not isinstance(data, dict)
        or data.get("schema") != SCHEMA
        or data.get("schema_version") != SCHEMA_VERSION
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
                field = PREFIX + name
                if not isinstance(record.get(field), list) or any(
                    not isinstance(name, str) for name in record[field]
                ):
                    raise ValueError(f"{resource}: invalid curated people list")


def validate_api_registry(data):
    """Validate stored source-registry structure before using its counts."""
    if (
        not isinstance(data, dict)
        or data.get("schema") != API_SCHEMA
        or data.get("schema_version") != 1
        or not isinstance(data.get("source"), dict)
        or data["source"].get("selection") != "all-accessible"
        or not isinstance(data.get("counts"), dict)
    ):
        raise ValueError("Destination is not a supported GLANCE API registry")
    for name in RESOURCES:
        records = data.get(name)
        if not isinstance(records, list) or not records:
            raise ValueError(f"{name}: missing or empty records")
        keys = [record_key(record, name) for record in records]
        if len(set(keys)) != len(keys) or data["counts"].get(name) != len(keys):
            raise ValueError(f"{name}: inconsistent registry counts or identifiers")
