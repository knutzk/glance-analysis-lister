# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Download a complete, typed GLANCE API source registry using stare.

This format preserves independent source records and their nested metadata.
It is deliberately distinct from the curated registry used by renderers.
"""

import json
import logging
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from ..provenance import generator_metadata
from ..registry.schema import (
    API_SCHEMA as SCHEMA,
    RESOURCES,
    record_key,
    validate_api_registry as validate_registry,
)
from ..storage import atomic_write_text
from .errors import endpoint_label, http_failure

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 500
# stare documents sort_by as a camelCase API field; these are the model aliases
# identifying records on the four detailed resource endpoints.
SORT_FIELDS = {
    "analyses": "referenceCode",
    "papers": "referenceCode",
    "confnotes": "temporaryReferenceCode",
    "pubnotes": "temporaryReferenceCode",
}


def _validate_page_size(page_size):
    if type(page_size) is not int or page_size < 1:
        raise ValueError("page_size must be a positive integer")


class _PaginationError(ValueError):
    """A locally generated completeness error containing no source values."""


class _ResponseError(ValueError):
    """A locally generated response-shape error containing no source values."""


def _failure_reason(error, stage):
    # Keep stare lazy: offline registry/view imports do not need its transport.
    from stare.exceptions import (
        ApiError,
        AuthenticationError,
        NetworkError,
        ResponseParseError,
    )

    if isinstance(error, _PaginationError):
        return f"Pagination failed: {error}. Retry the complete download; --allow-count-drop cannot bypass this check."
    if isinstance(error, _ResponseError):
        return f"Response validation failed: {error}. Check client/API compatibility; no records were skipped."
    if isinstance(error, ResponseParseError):
        return "Response validation failed; check client/API compatibility. No records were skipped."
    if isinstance(error, ApiError):
        return http_failure(error.status_code)
    if isinstance(error, NetworkError):
        return "Network request failed; check connectivity, proxy and TLS/CA settings, then retry when the service is reachable."
    if isinstance(error, AuthenticationError) or stage == "authentication":
        return "Authentication failed; retry with --login. If it persists, check account access and authentication-service connectivity."
    if stage == "configuration":
        return "Client configuration failed; check stare settings and the installed dependencies."
    return "Unexpected retrieval failure; check client/API compatibility and report the exception type with a synthetic reproducer."


def collect_registry(client, *, page_size=DEFAULT_PAGE_SIZE, client_version=None):
    """Collect all four resources; reject incomplete or inconsistent pagination.

    No query is supplied: this records all records accessible to the caller.
    Exceptions abort the entire candidate, never silently skip a record.
    """
    _validate_page_size(page_size)
    data = {}
    counts = {}
    for resource_number, name in enumerate(RESOURCES, 1):
        logger.info(
            "Fetching %s (%d/%d); sort=%s ascending",
            name,
            resource_number,
            len(RESOURCES),
            SORT_FIELDS[name],
        )
        resource_started = perf_counter()
        page_number = 0
        records = {}
        total = None
        offset = 0
        while total is None or offset < total:
            page_number += 1
            logger.debug(
                "Requesting %s page %d: offset=%d, limit=%d",
                name,
                page_number,
                offset,
                page_size,
            )
            page_started = perf_counter()
            try:
                result = getattr(client, name).search(
                    offset=offset,
                    limit=page_size,
                    sort_by=SORT_FIELDS[name],
                    sort_desc=False,
                )
            except ValueError:
                # JSON/model validation exceptions can include the entire response.
                raise _ResponseError(f"{name}: invalid JSON or model fields") from None
            count = result.number_of_results
            if type(count) is not int or count < 1:
                raise _PaginationError(f"{name}: empty or invalid result count")
            if total is not None and count != total:
                raise _PaginationError(f"{name}: count changed during pagination")
            total = count
            batch = result.results
            if not batch or len(batch) > page_size or offset + len(batch) > total:
                raise _PaginationError(f"{name}: incomplete or invalid page")
            for model in batch:
                try:
                    record = model.model_dump(mode="json", by_alias=True)
                    key = record_key(record, name)
                except (ValueError, TypeError):
                    raise _ResponseError(
                        f"{name}: invalid record or missing native identifier"
                    ) from None
                if key in records:
                    raise _PaginationError(f"{name}: duplicate record across pages")
                records[key] = record
            offset += len(batch)
            logger.info(
                "API %s: %d/%d records (page %d, %.2fs)",
                name,
                offset,
                total,
                page_number,
                perf_counter() - page_started,
            )
        data[name] = [records[key] for key in sorted(records)]
        counts[name] = total
        logger.info(
            "Finished %s: %d records, %d pages, %.2fs",
            name,
            total,
            page_number,
            perf_counter() - resource_started,
        )
    return {
        "schema": SCHEMA,
        "generator": generator_metadata(),
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": {
            "client": "stare",
            "client_version": client_version,
            "selection": "all-accessible",
            "representation": "validated-models",
            "page_size": page_size,
            "sort_fields": dict(SORT_FIELDS),
            "sort_descending": False,
        },
        "counts": counts,
        **data,
    }


def publish_registry(candidate, destination, *, allow_count_drop=False):
    """Validate a whole candidate and atomically publish it last."""
    logger.info("Validating complete API snapshot before publication")
    validate_registry(candidate)
    destination = Path(destination)
    if destination.exists():
        logger.info("Checking existing API snapshot and count changes: %s", destination)
        previous = json.loads(destination.read_text(encoding="utf-8"))
        validate_registry(previous)
        if candidate["source"].get("base_url") != previous["source"].get("base_url"):
            raise ValueError("API endpoint differs; use a separate destination")
        for name in RESOURCES:
            logger.info(
                "Count check %s: previous=%d, downloaded=%d",
                name,
                previous["counts"][name],
                candidate["counts"][name],
            )
            if (
                not allow_count_drop
                and candidate["counts"][name] < previous["counts"][name] * 0.8
            ):
                raise ValueError(f"{name}: count dropped by more than 20%")
    else:
        logger.info("No existing API snapshot; this is the first publication")
    logger.info("Publishing API snapshot atomically: %s", destination)
    atomic_write_text(
        destination, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    )
    logger.info("Published API snapshot: %s", destination)


def download_registry(
    destination, *, login=False, allow_count_drop=False, page_size=DEFAULT_PAGE_SIZE
):
    """Use browser SSO and fetch live data without response caching."""
    _validate_page_size(page_size)
    try:
        from stare import Glance
        from stare.auth import TokenManager
        from stare.settings import StareSettings
    except ImportError:
        raise ValueError(
            "stare is missing; reinstall glance-grove with its dependencies"
        ) from None

    stage = "configuration"
    try:
        settings = StareSettings(cache_enabled=False)
        client_version = version("stare")
        logger.info(
            "Starting API download with stare %s; output=%s",
            client_version,
            destination,
        )
        logger.info("API endpoint: %s", endpoint_label(settings.base_url))
        logger.info(
            "Configuration: page_size=%d; all accessible records; sequential retrieval; response cache disabled",
            page_size,
        )
        logger.info(
            "Count-drop protection: %s",
            "override enabled (schema and endpoint checks remain active)"
            if allow_count_drop
            else "reject drops greater than 20%",
        )
        logger.info(
            "Authentication: %s; credentials and token refresh managed by stare",
            "browser SSO requested" if login else "using stored credentials",
        )
        stage = "authentication"
        manager = TokenManager(settings)
        if login:
            logger.info("Complete CERN SSO in your browser.")
            manager.login()
        logger.info("Opening one shared GLANCE client with TLS verification enabled")
        stage = "retrieval"
        with Glance(settings=settings, token_manager=manager) as client:
            candidate = collect_registry(
                client, page_size=page_size, client_version=client_version
            )
    except Exception as exc:
        # Never stringify upstream exceptions or retain their chain in CLI traces.
        raise ValueError(
            f"GLANCE API download failed ({type(exc).__name__}); no registry published. "
            + _failure_reason(exc, stage)
        ) from None
    candidate["source"]["base_url"] = settings.base_url
    publish_registry(candidate, destination, allow_count_drop=allow_count_drop)
    return candidate["counts"]
