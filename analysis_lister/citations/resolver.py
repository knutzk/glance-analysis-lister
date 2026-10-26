# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Citation resolver: isolated concerns with no registry model dependency."""

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import requests

from ..diagnostics import lookup_notice, lookup_report
from .inspire import InspireClient, inspire_citation
from .store import load_store, normalize_doi, save_store

logger = logging.getLogger(__name__)


JHEP = re.compile(r"10\.1007/jhep(0[1-9]|1[0-2])\((\d{4})\)(\d{3,})", re.I)


def infer_citation(doi):
    """Infer only a fully specified JHEP citation; material remains unknown."""
    match = JHEP.fullmatch(normalize_doi(doi))
    if match is None:
        return None
    month, year, article = match.groups()
    return {
        "citation": f"JHEP {month} ({year}) {article}",
        "source": "doi-pattern:jhep",
    }


def snapshot_dois(path: Path):
    """Read DOI inputs only, without reconstructing private analysis records."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Snapshot must be an object")
    result = set()
    malformed = 0
    if data.get("schema") in {"glance-api-registry", "glance-curated-registry"}:
        from ..registry.publication_dois import paper_dois

        if not isinstance(data.get("papers"), list):
            raise ValueError("Snapshot requires a papers list")
        for paper in data["papers"]:
            if not isinstance(paper, dict):
                raise ValueError("Invalid paper record")
            dois, invalid = paper_dois(paper)
            result.update(dois)
            malformed += invalid
    else:
        raise ValueError("Unsupported DOI snapshot format")
    if malformed:
        lookup_notice(
            logger,
            logging.WARNING,
            "Skipped %d malformed DOI values in snapshot; valid DOIs will still be processed",
            malformed,
        )
    return result


@lookup_report()
def resolve_dois(dois, cache_path: Path, *, method="infer", refresh=False, limit=None):
    """Resolve missing entries; atomically checkpoint each success, never failures."""
    if method not in {"infer", "inspire", "auto"}:
        raise ValueError("Unknown DOI resolution method")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Resolution limit must be positive")
    inputs = sorted({normalize_doi(doi) for doi in dois})
    logger.info("Resolving citations for %s DOIs using %s", f"{len(inputs):,}", method)
    records = load_store(cache_path)
    summary = Counter(
        resolved=0, existing=0, locked=0, unresolved=0, failed=0, deferred=0
    )
    client = None
    attempted = 0
    try:
        for doi in inputs:
            previous = records.get(doi)
            if previous is not None:
                if previous["source"] == "manual":
                    summary["locked"] += 1
                    continue
                if not refresh:
                    summary["existing"] += 1
                    continue
            if limit is not None and attempted >= limit:
                summary["deferred"] += 1
                continue
            attempted += 1
            if attempted == 1 or attempted % 25 == 0:
                logger.info(
                    "Citation lookup %s; %s resolved so far",
                    f"{attempted:,}",
                    f"{summary['resolved']:,}",
                )
            logger.debug("Resolving DOI %s", doi)
            try:
                record = infer_citation(doi) if method in {"infer", "auto"} else None
                if record is None and method in {"inspire", "auto"}:
                    if client is None:
                        client = InspireClient()
                    payload = client.fetch(doi)
                    record = (
                        inspire_citation(doi, payload) if payload is not None else None
                    )
                if record is None:
                    summary["unresolved"] += 1
                    lookup_notice(
                        logger,
                        logging.WARNING,
                        "%s: no citation resolved; entry remains retryable",
                        doi,
                    )
                    continue
            except requests.RequestException:
                summary["failed"] += 1
                lookup_notice(
                    logger,
                    logging.WARNING,
                    "%s: INSPIRE request failed; entry remains retryable",
                    doi,
                )
                continue
            except ValueError as error:
                summary["unresolved"] += 1
                lookup_notice(
                    logger,
                    logging.WARNING,
                    "%s: %s; entry remains retryable",
                    doi,
                    error,
                )
                continue
            record["resolved_at"] = datetime.now(UTC).isoformat()
            if (
                previous is not None
                and previous.get("material", "unknown") != "unknown"
                and record.get("material", "unknown") == "unknown"
            ):
                summary["existing"] += 1
                continue
            records[doi] = record
            save_store(cache_path, records)
            summary["resolved"] += 1
        save_store(cache_path, records)
    finally:
        if client is not None:
            client.close()
    return dict(summary)
