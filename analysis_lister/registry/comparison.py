# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline record comparisons for like-for-like API or curated snapshots."""

import json
from hashlib import sha256
from pathlib import Path

from ..storage import atomic_write_text
from .schema import (
    API_SCHEMA,
    RESOURCES,
    SCHEMA,
    record_key,
    validate_api_registry,
    validate_registry,
)


def _changes(before, after, path=""):
    """Use JSON Pointer paths; distinguish absent keys from explicit nulls.

    Lists are compared as ordered values. In particular, DOI/correction order
    must not be normalised away. Dictionary order never constitutes a change.
    """
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before:
                yield {"path": pointer, "kind": "added", "after": after[key]}
            elif key not in after:
                yield {"path": pointer, "kind": "removed", "before": before[key]}
            else:
                yield from _changes(before[key], after[key], pointer)
    elif json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True):
        yield {"path": path, "kind": "changed", "before": before, "after": after}


def compare_snapshots(before, after):
    """Compare validated record collections, ignoring container build metadata."""
    for data in (before, after):
        schema = data.get("schema") if isinstance(data, dict) else None
        if not isinstance(schema, str):
            raise ValueError("Comparison requires an API or curated registry")
        validator = {API_SCHEMA: validate_api_registry, SCHEMA: validate_registry}.get(
            schema
        )
        if validator is None:
            raise ValueError("Comparison requires an API or curated registry")
        validator(data)
        if not isinstance(data.get("source", {}), dict):
            raise ValueError("Snapshot source must be an object")
    if before["schema"] != after["schema"]:
        raise ValueError(
            "Compare two API snapshots or two curated snapshots, not different formats"
        )
    if before.get("source", {}).get("base_url") != after.get("source", {}).get(
        "base_url"
    ):
        raise ValueError("Snapshots use different API endpoints")
    resources = {}
    for resource in RESOURCES:
        old = {record_key(record, resource): record for record in before[resource]}
        new = {record_key(record, resource): record for record in after[resource]}
        added, removed = (
            sorted(new.keys() - old.keys()),
            sorted(old.keys() - new.keys()),
        )
        changed = []
        for reference in sorted(old.keys() & new.keys()):
            fields = list(_changes(old[reference], new[reference]))
            if fields:
                changed.append({"reference": reference, "fields": fields})
        resources[resource] = {
            "counts": {
                "before": len(old),
                "after": len(new),
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": len(old.keys() & new.keys()) - len(changed),
            },
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    return {
        "schema": "glance-snapshot-comparison",
        "schema_version": 1,
        "snapshot_schema": before["schema"],
        "scope": "records only; container timestamps and build metadata excluded; list order is significant",
        "resources": resources,
    }


def compare_files(before_path, after_path, *, output=None):
    """Optionally publish a detailed JSON report without modifying either input."""
    paths = [Path(before_path), Path(after_path)]
    if output is not None and any(
        Path(output).resolve() == path.resolve() for path in paths
    ):
        raise ValueError("Comparison output must not overwrite an input snapshot")
    raw = [path.read_bytes() for path in paths]
    data = [json.loads(value.decode("utf-8")) for value in raw]
    report = compare_snapshots(*data)
    report["inputs"] = {
        label: {
            "path": str(path),
            "sha256": sha256(value).hexdigest(),
            "fetched_at": snapshot.get("fetched_at"),
        }
        for label, path, value, snapshot in zip(
            ("before", "after"), paths, raw, data, strict=True
        )
    }
    if output is not None:
        atomic_write_text(
            Path(output), json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    return report
