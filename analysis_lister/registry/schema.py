# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Resource identities and offline contract validation, independent of views."""

import json
from functools import cache
from importlib.resources import files

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


@cache
def _curated_validator():
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads(
        files(__package__)
        .joinpath("schemas/curated-v2.schema.json")
        .read_text(encoding="utf-8")
    )
    # rfc3339-validator is an explicit dependency: date-time must not silently
    # become an annotation when optional format dependencies are absent.
    return Draft202012Validator(
        schema, format_checker=FormatChecker(formats=("date", "date-time"))
    )


def validate_registry(data):
    """Validate v2 structure, then cross-record integrity, without changing data.

    Unknown additions are accepted. Unsupported versions are never guessed or
    silently interpreted as v2. Validation and reference lookup remain offline.
    """
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("Destination is not a supported curated registry")
    if (
        type(data.get("schema_version")) is not int
        or data["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError(
            "Destination is not a supported curated registry: expected schema_version 2"
        )
    error = next(_curated_validator().iter_errors(data), None)
    if error is not None:
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        # Never include instance values (which can contain private records).
        detail = f"failed {error.validator} validation"
        if error.validator == "required":
            missing = [
                key for key in error.validator_value if key not in error.instance
            ]
            detail = "missing required field(s): " + ", ".join(missing)
        elif error.validator == "type":
            detail = f"expected {error.validator_value}"
        elif error.validator == "anyOf" and "title" in error.schema:
            detail = f"expected {error.schema['title']}"
        elif error.validator == "format":
            detail = f"expected {error.validator_value}"
        raise ValueError(f"Curated registry {path}: {detail}")
    for resource in RESOURCES:
        keys = [record_key(record, resource) for record in data[resource]]
        if len(keys) != len(set(keys)) or data["counts"][resource] != len(keys):
            raise ValueError(f"{resource}: inconsistent counts or identifiers")


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
