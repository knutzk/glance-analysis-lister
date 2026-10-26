# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build and atomically publish curated registries from saved downloads."""

import json
import logging
from pathlib import Path

from ..citations.store import DEFAULT_CACHE, default_store_path, load_store
from ..storage import atomic_write_text
from .enrichment import curate
from .public_identifiers import default_identifiers_path, load_identifiers
from .schema import RESOURCES, validate_registry

logger = logging.getLogger(__name__)


def build_registry(
    api_path,
    output,
    *,
    allow_count_drop=False,
    doi_cache=DEFAULT_CACHE,
    pubnote_identifiers=None,
):
    """Build offline and atomically publish without overwriting source inputs."""
    api_path, output = Path(api_path), Path(output)
    identifier_path = (
        Path(pubnote_identifiers)
        if pubnote_identifiers is not None
        else default_identifiers_path()
    )
    citation_path = Path(doi_cache)
    if citation_path == DEFAULT_CACHE and not citation_path.exists():
        citation_path = default_store_path()
    inputs = [api_path, citation_path, identifier_path]
    if any(output.resolve() == path.resolve() for path in inputs):
        raise ValueError("Registry output must not overwrite an input")
    api = json.loads(api_path.read_text(encoding="utf-8"))
    candidate = curate(
        api,
        citations=load_store(citation_path),
        pubnote_identifiers=load_identifiers(identifier_path),
    )
    validate_registry(candidate)
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        validate_registry(previous)
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
    for resource, counts in candidate["gal_curation"][
        "public_identifier_statistics"
    ].items():
        logger.info("Public identifiers %s: %s", resource, counts)
    return candidate["counts"]
