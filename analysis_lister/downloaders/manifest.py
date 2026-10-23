# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Fixed provenance for complete, unfiltered HTML download batches."""

import json
from datetime import UTC, datetime
from pathlib import Path

from ..storage import SUPPLEMENT_MANIFEST


def make_manifest(tasks):
    return {
        "schema": "glance-csv-supplements",
        "schema_version": 2,
        "selection": "all-accessible",
        "fetched_at": datetime.now(UTC).isoformat(),
        "tables": {task.name: list(task.columns) for task in tasks},
    }


def validate_manifest(manifest, tasks):
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "glance-csv-supplements"
        or manifest.get("schema_version") != 2
        or manifest.get("selection") != "all-accessible"
        or manifest.get("tables") != {task.name: list(task.columns) for task in tasks}
    ):
        raise ValueError(
            "Unsupported supplemental CSV manifest; expected a complete all-accessible batch"
        )
    return manifest


def read_manifest(directory, tasks):
    path = Path(directory) / SUPPLEMENT_MANIFEST
    return validate_manifest(json.loads(path.read_text(encoding="utf-8")), tasks)
