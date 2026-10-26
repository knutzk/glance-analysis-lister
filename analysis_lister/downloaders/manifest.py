# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Fixed provenance for complete, unfiltered HTML download batches."""

import json
from datetime import UTC, datetime
from pathlib import Path

CSV_REFRESH_MARKER = ".html-download-in-progress"
HTML_MANIFEST = "html_manifest.json"


def make_manifest(tasks):
    return {
        "schema": "glance-html-csv",
        "schema_version": 1,
        "selection": "all-accessible",
        "fetched_at": datetime.now(UTC).isoformat(),
        "tables": {task.name: [] for task in tasks},
    }


def validate_manifest(manifest, tasks):
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "glance-html-csv"
        or manifest.get("schema_version") != 1
        or manifest.get("selection") != "all-accessible"
        or manifest.get("tables") != {task.name: [] for task in tasks}
    ):
        raise ValueError(
            "Unsupported HTML CSV manifest; expected a complete all-accessible batch"
        )
    return manifest


def read_manifest(directory, tasks):
    path = Path(directory) / HTML_MANIFEST
    return validate_manifest(json.loads(path.read_text(encoding="utf-8")), tasks)
