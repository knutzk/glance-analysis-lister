# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Scale only the maintained public demo, preserving each four-record cohort."""

import json
from copy import deepcopy
from pathlib import Path

RESOURCES = ("analyses", "papers", "confnotes", "pubnotes")
FIXTURE = Path(__file__).resolve().parents[2] / "examples/synthetic_registry.json"


def synthetic_registry(records):
    if records < 4 or records % 4:
        raise ValueError("Records per category must be a positive multiple of four")
    source = json.loads(FIXTURE.read_text())
    if any(len(source[resource]) != 4 for resource in RESOURCES):
        raise ValueError("Review the benchmark when the four-record demo changes")
    result = deepcopy(source)
    for resource in RESOURCES:
        result[resource] = []
    for cohort in range(records // 4):
        # Map identities and relationship targets together, including public IDs.
        identities = {}
        for resource in RESOURCES:
            for index, record in enumerate(source[resource]):
                for field in (
                    "referenceCode",
                    "temporaryReferenceCode",
                    "finalReferenceCode",
                ):
                    if field in record:
                        value = record[field]
                        prefix, _, _ = value.rpartition("-")
                        identities[value] = f"{prefix}-{cohort * 4 + index + 1:06d}"

        def remap(value, identities=identities):
            if isinstance(value, dict):
                return {key: remap(item) for key, item in value.items()}
            if isinstance(value, list):
                return [remap(item) for item in value]
            return identities.get(value, value) if isinstance(value, str) else value

        for resource in RESOURCES:
            result[resource].extend(remap(source[resource]))
    result["counts"] = dict.fromkeys(RESOURCES, records)
    stats = result["gal_curation"]["doi_statistics"]
    for key in stats:
        stats[key] *= records // 4
    return result
