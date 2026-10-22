# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Download a complete, typed GLANCE API source registry using stare.

This format preserves independent source records and their nested metadata.
It is deliberately distinct from the enriched CSV registry used by renderers.
"""

import json
import logging
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ..registry.schema import (
    API_SCHEMA as SCHEMA,
    RESOURCES,
    record_key,
    validate_api_registry as validate_registry,
)
from ..storage import atomic_write_text

logger = logging.getLogger(__name__)


def collect_registry(client, *, page_size=100, client_version=None):
    """Collect all four resources; reject incomplete or inconsistent pagination.

    No query is supplied: this records all records accessible to the caller.
    Exceptions abort the entire candidate, never silently skip a record.
    """
    if type(page_size) is not int or page_size < 1:
        raise ValueError("page_size must be a positive integer")
    data = {}
    counts = {}
    for name in RESOURCES:
        records = {}
        total = None
        offset = 0
        while total is None or offset < total:
            result = getattr(client, name).search(offset=offset, limit=page_size)
            count = result.number_of_results
            if type(count) is not int or count < 1:
                raise ValueError(f"{name}: empty or invalid result count")
            if total is not None and count != total:
                raise ValueError(f"{name}: count changed during pagination; retry")
            total = count
            batch = result.results
            if not batch or len(batch) > page_size or offset + len(batch) > total:
                raise ValueError(f"{name}: incomplete or invalid page")
            for model in batch:
                record = model.model_dump(mode="json", by_alias=True)
                key = record_key(record, name)
                if key in records:
                    raise ValueError(f"{name}: duplicate record across pages")
                records[key] = record
            offset += len(batch)
            logger.info("API %s: %d/%d", name, offset, total)
        data[name] = [records[key] for key in sorted(records)]
        counts[name] = total
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": {
            "client": "stare",
            "client_version": client_version,
            "selection": "all-accessible",
            "representation": "validated-models",
        },
        "counts": counts,
        **data,
    }


def publish_registry(candidate, destination, *, allow_count_drop=False):
    """Validate a whole candidate and atomically publish it last."""
    validate_registry(candidate)
    destination = Path(destination)
    if destination.exists():
        previous = json.loads(destination.read_text(encoding="utf-8"))
        validate_registry(previous)
        if candidate["source"].get("base_url") != previous["source"].get("base_url"):
            raise ValueError("API endpoint differs; use a separate destination")
        for name in RESOURCES:
            if (
                not allow_count_drop
                and candidate["counts"][name] < previous["counts"][name] * 0.8
            ):
                raise ValueError(f"{name}: count dropped by more than 20%")
    atomic_write_text(
        destination, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    )


def download_registry(destination, *, login=False, allow_count_drop=False):
    """Use browser SSO and fetch live data without Selenium or response caching."""
    try:
        from stare import Glance
        from stare.auth import TokenManager
        from stare.settings import StareSettings
    except ImportError:
        raise ValueError(
            "stare is missing; reinstall glance-analysis-lister with its dependencies"
        ) from None

    try:
        settings = StareSettings(cache_enabled=False)
        manager = TokenManager(settings)
        if login:
            logger.info("Complete CERN SSO in your browser.")
            manager.login()
        with Glance(settings=settings, token_manager=manager) as client:
            candidate = collect_registry(client, client_version=version("stare"))
    except Exception as exc:
        # Model-validation errors can include private records. The command
        # reports the exception type, without serialising the response or tokens.
        raise ValueError(
            f"GLANCE API download failed ({type(exc).__name__}); no registry published. "
            "If authentication expired, retry with --login."
        ) from None
    candidate["source"]["base_url"] = settings.base_url
    publish_registry(candidate, destination, allow_count_drop=allow_count_drop)
    return candidate["counts"]
