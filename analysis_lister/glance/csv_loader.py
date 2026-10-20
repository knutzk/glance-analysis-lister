# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Read validated CSV batches and assemble registries without owning their state."""

import csv
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..retrieval import read_scope
from ..storage import require_complete_csv_batch
from .analysis import Analysis
from .confnote import ConfNote
from .field_maps import (
    REQUIRED_COLUMNS_ANALYSIS,
    REQUIRED_COLUMNS_CONFNOTE,
    REQUIRED_COLUMNS_PAPER,
    REQUIRED_COLUMNS_PUBNOTE,
)
from .paper import Paper
from .pubnote import PubNote

logger = logging.getLogger(__name__)


def load_csv_registry(
    registry_cls,
    csv_dir: Path,
    *,
    analysis_csv,
    paper_csv,
    confnote_csv,
    pubnote_csv,
    threshold_year,
):
    """Load a complete batch, preserving enrichment order and diagnostics."""
    paths = [
        csv_dir / name for name in (analysis_csv, paper_csv, confnote_csv, pubnote_csv)
    ]
    require_complete_csv_batch(csv_dir)
    last_modified_time = determine_last_modified_time(paths)
    logger.info("Loading list of analyses from file %s", paths[0].name)
    rows = read_csv_rows(
        paths[0], REQUIRED_COLUMNS_ANALYSIS, key="Reference Code", prefix="ANA-"
    )
    entries = sorted(
        (Analysis.from_csv_dict(row) for row in rows), key=lambda entry: entry.ref_code
    )
    registry = registry_cls(
        {entry.ref_code: entry for entry in entries},
        threshold_year=threshold_year,
        last_modified_time=last_modified_time,
    )
    registry.retrieval_scope = read_scope(csv_dir)
    logger.info("Loaded %d analysis base entries.", len(entries))
    for path, cls, columns, key, prefix, label, listed in (
        (
            paths[1],
            Paper,
            REQUIRED_COLUMNS_PAPER,
            "Reference Code",
            "",
            "paper",
            "papers",
        ),
        (
            paths[2],
            ConfNote,
            REQUIRED_COLUMNS_CONFNOTE,
            "Temporary Reference Code",
            "CONF-",
            "CONF note",
            "confnotes",
        ),
        (
            paths[3],
            PubNote,
            REQUIRED_COLUMNS_PUBNOTE,
            "Temporary Reference Code",
            "PUB-",
            "PUB note",
            "pubnotes",
        ),
    ):
        logger.info("Loading list of %s records from file %s", label, path.name)
        rows = read_csv_rows(path, columns, key=key, prefix=prefix)
        enriched, unmatched = registry.enrich(rows, cls, key=key, prefix=prefix)
        log_enrichment(label, enriched, unmatched, len(getattr(registry, listed)))
    registry.log_unaccounted()
    require_complete_csv_batch(csv_dir)
    return registry


def determine_last_modified_time(paths: list[Path]) -> str:
    """Return the latest modification timestamp for CSV files as string."""
    max_timestamp = 0
    for path in paths:
        try:
            ts = path.stat().st_mtime
            max_timestamp = max(max_timestamp, ts)
        except FileNotFoundError:
            continue

    # Formatting a timestamp of 0 would put "Jan 01, 1970" on every page
    # rather than admitting that there was nothing to read it from.
    if not max_timestamp:
        logger.warning("No CSV file found, cannot determine the sync time.")
        return "unknown"

    last_modified = datetime.fromtimestamp(max_timestamp, tz=ZoneInfo("Europe/Zurich"))
    return last_modified.strftime("%b %d, %Y, %H:%M (%Z)")


def log_enrichment(label: str, enriched: int, unmatched: int, listed: int):
    """Report the outcome of one enrichment step.

    Args:
        label: Name of the enrichment type, for the log message.
        enriched: Number of analyses that were enriched.
        unmatched: Number of rows without a matching analysis.
        listed: Number of enriched entries that the pages end up listing.

    """
    logger.info(
        "Enriched %d analyses with %s data, of which %d are listed on the "
        "pages. %d %s rows had no matching analysis.",
        enriched,
        label,
        listed,
        unmatched,
        label,
    )


def read_csv_rows(
    path: Path, required_columns=(), *, key=None, prefix=""
) -> list[dict[str, str]]:
    """Return the rows of one CSV file.

    All four files are required. Carrying on without one of them used to
    cost the pages a whole category — every paper, or every note — and
    the run reported that as a plain count, which reads exactly like a
    quiet week in the top WG. Failing here instead keeps a half-read
    download out of the committed snapshot.

    Args:
        path: Path of the CSV file to read.

    Returns:
        One dictionary per row of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If headers, row widths, identifiers, or uniqueness are
            invalid, or the file holds no rows. Values are never stripped.

    """
    try:
        with open(path, encoding="utf8", newline="") as f:
            reader = csv.DictReader(f, strict=True)
            headers = reader.fieldnames or []
            duplicates = [h for h, n in Counter(headers).items() if n > 1]
            missing = sorted(set(required_columns) - set(headers))
            if duplicates or missing or any(not h for h in headers):
                raise ValueError(
                    f"{path}: invalid CSV headers; missing={missing}, "
                    f"duplicates={duplicates}, empty headers={'' in headers}"
                )
            rows = []
            seen = {}
            for row in reader:
                line = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{path}: line {line}: wrong number of CSV fields")
                if key is not None:
                    ref = row[key].removeprefix(prefix)
                    if not re.fullmatch(r"[A-Z][A-Z0-9]+-\d{4}-\d+", ref):
                        raise ValueError(
                            f"{path}: line {line}: invalid {key}: {row[key]!r}"
                        )
                    if ref in seen:
                        raise ValueError(
                            f"{path}: line {line}: duplicate identifier {ref}; "
                            f"first seen on line {seen[ref]}"
                        )
                    seen[ref] = line
                rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"{path}: line {reader.line_num}: invalid CSV: {exc}") from exc
    except FileNotFoundError:
        raise FileNotFoundError(
            f"{path} not found. Re-run analysis_lists.py download (step 1)."
        ) from None

    if not rows:
        raise ValueError(
            f"{path} holds no rows. GLANCE probably returned a login page; "
            "refresh the cookies and re-run analysis_lists.py download (step 1)."
        )

    return rows
