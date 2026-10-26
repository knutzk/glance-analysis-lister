# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build and atomically publish curated registries from saved downloads."""

import json
import logging
from pathlib import Path
from time import perf_counter

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
    started = perf_counter()
    api_path, output = Path(api_path), Path(output)
    logger.info(
        "Starting API-only registry build (offline; no HTML or external requests)"
    )
    logger.info("Files: API input=%s; curated output=%s", api_path, output)
    logger.info(
        "Count-drop protection: %s",
        "override enabled (schema and endpoint checks remain active)"
        if allow_count_drop
        else "reject drops greater than 20%",
    )
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
    logger.info("Loading saved API snapshot: %s", api_path)
    api_bytes = api_path.read_bytes()
    input_size = len(api_bytes)
    api = json.loads(api_bytes.decode("utf-8"))
    del api_bytes
    logger.info("Loading shared DOI dictionary: %s", citation_path)
    citations = load_store(citation_path)
    logger.info("Loading shared PUB-note identifier dictionary: %s", identifier_path)
    identifiers = load_identifiers(identifier_path)
    logger.info(
        "Loaded %d DOI entries and %d CDS-to-PUB identifier associations",
        len(citations),
        len(identifiers),
    )
    logger.info(
        "Curating API records: people roles, compact lists, public identifiers and cached DOI metadata"
    )
    candidate = curate(api, citations=citations, pubnote_identifiers=identifiers)
    logger.info("Validating complete curated registry")
    validate_registry(candidate)
    if output.exists():
        logger.info("Checking existing curated registry and count changes: %s", output)
        previous = json.loads(output.read_text(encoding="utf-8"))
        validate_registry(previous)
        if previous.get("source", {}).get("base_url") != candidate["source"].get(
            "base_url"
        ):
            raise ValueError("API endpoint differs; choose a new output")
        for resource in RESOURCES:
            logger.info(
                "Count check %s: previous=%d, candidate=%d",
                resource,
                previous["counts"][resource],
                candidate["counts"][resource],
            )
            if (
                not allow_count_drop
                and candidate["counts"][resource] < previous["counts"][resource] * 0.8
            ):
                raise ValueError(f"{resource}: count dropped by more than 20%")
    else:
        logger.info("No existing curated registry; this is the first build")
    logger.info("Publishing curated registry atomically: %s", output)
    serialized = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    output_size = len(serialized.encode("utf-8"))
    atomic_write_text(output, serialized)
    logger.info(
        "Registry file sizes: API input %d bytes (%.2f MiB); curated output %d bytes (%.2f MiB); "
        "%d bytes %s (%.1f%%). Sizes include JSON formatting and build metadata",
        input_size,
        input_size / 1024**2,
        output_size,
        output_size / 1024**2,
        abs(input_size - output_size),
        "smaller" if output_size <= input_size else "larger",
        100 * abs(input_size - output_size) / input_size,
    )
    for resource, counts in candidate["gal_curation"][
        "public_identifier_statistics"
    ].items():
        logger.info(
            "Public identifier sources for %s: %s",
            resource,
            ", ".join(f"{source}={count}" for source, count in sorted(counts.items())),
        )
    doi = candidate["gal_curation"]["doi_statistics"]
    logger.info(
        "DOI summary: %d papers with DOIs; %d resolved citations; %d unresolved; %d malformed links",
        doi["papers_with_dois"],
        doi["resolved"],
        doi["unresolved"],
        doi["malformed_links"],
    )
    logger.info(
        "Published curated registry: %s (%.2fs)", output, perf_counter() - started
    )
    return candidate["counts"]
