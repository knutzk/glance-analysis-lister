# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build and atomically publish curated registries from saved downloads."""

import json
import logging
from pathlib import Path

from ..citations.store import DEFAULT_CACHE, load_store
from ..downloaders.csv_io import read_csv_rows
from ..downloaders.html import download_tasks
from ..downloaders.scope import SCOPE_FILENAME, RetrievalScope, check_scope, read_scope
from ..storage import SUPPLEMENT_MANIFEST, atomic_write_text, require_complete_csv_batch
from .enrichment import curate
from .schema import RESOURCES, validate_registry

logger = logging.getLogger(__name__)


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
            previous.get("gal_curation", {})
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
