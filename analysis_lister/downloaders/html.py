# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Authenticated GLANCE downloads and staged HTML-to-CSV conversion."""

import csv
import json
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from attrs import field, frozen

from analysis_lister.downloaders.csv_io import read_csv_rows
from analysis_lister.downloaders.tables import (
    parse_html_table,
    table_to_rows,
    validate_table_completeness,
)
from analysis_lister.storage import CSV_REFRESH_MARKER, SUPPLEMENT_MANIFEST

from . import http
from .manifest import make_manifest, read_manifest

logger = logging.getLogger(__name__)


class HTMLParser:
    @staticmethod
    def parse_to_csv(
        html: str,
        output_csv: Path,
        debug_path: Path | None = None,
        column_filter: Sequence[str] | None = None,
    ) -> None:
        """Save diagnostic HTML, then validate and write a complete CSV table."""
        source = str(output_csv)
        logger.debug("Parsing HTML content to extract table data for %s", source)
        table = parse_html_table(html, source=source)
        # Keep diagnostic HTML even if header or row validation subsequently fails.
        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(
                html + ("" if html.endswith("\n") else "\n"), encoding="utf-8"
            )
            logger.debug(
                "Full response including result counters saved to %s", debug_path
            )

        csv_data = table_to_rows(table, source=source, column_filter=column_filter)
        validate_table_completeness(table, len(csv_data) - 1, source=source)
        with output_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)
        logger.debug("CSV file successfully generated: %s", output_csv)
        logger.info("%s: %s rows; complete", output_csv.stem, f"{len(csv_data) - 1:,}")


@frozen
class DownloadTable:
    """GLANCE table metadata; destinations are supplied to the workflow separately."""

    name: str
    url: str
    columns: tuple[str, ...] = field(converter=tuple)
    sort_by: str
    key: str | None = None
    prefix: str = ""

    @property
    def csv_filename(self) -> str:
        return f"{self.name}.csv"

    @property
    def html_filename(self) -> str:
        return f"{self.name}.html"


@contextmanager
def staged_csv_files(
    tasks: Sequence[DownloadTable],
    csv_dir: Path,
    debug_dir: Path,
    *,
    cookies: dict[str, str] | None = None,
    use_local_html: bool = False,
    debug: bool = False,
) -> Iterator[Path]:
    """Yield a complete CSV batch without modifying the current data."""
    if (
        any((csv_dir / task.csv_filename).exists() for task in tasks)
        or (csv_dir / SUPPLEMENT_MANIFEST).exists()
    ):
        read_manifest(csv_dir, tasks)
        for task in tasks:
            existing = csv_dir / task.csv_filename
            if task.key and existing.exists():
                with existing.open(encoding="utf-8", newline="") as stream:
                    headers = next(csv.reader(stream), [])
                if set(headers) != set(task.columns):
                    raise ValueError(
                        "Destination contains a different CSV format; use a separate "
                        "directory for API supplements (default: current working directory)."
                    )
    manifest = (
        read_manifest(debug_dir, tasks) if use_local_html else make_manifest(tasks)
    )
    csv_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so individual replacements are atomic.
    temporary = TemporaryDirectory(prefix=".refresh-", dir=csv_dir, delete=False)
    staging = Path(temporary.name)
    try:
        if debug and not use_local_html:
            (debug_dir / SUPPLEMENT_MANIFEST).unlink(missing_ok=True)
        for index, task in enumerate(tasks, start=1):
            logger.info(
                "%s %s (%d/%d)",
                "Reading saved" if use_local_html else "Retrieving",
                task.name,
                index,
                len(tasks),
            )
            if use_local_html:
                html = (debug_dir / task.html_filename).read_text(encoding="utf-8")
            else:
                html = http.DataFetcher.fetch_html(
                    task.url,
                    http.COMMON_PARAMS | {"s[0][name]": task.sort_by},
                    cookies,
                )
            HTMLParser.parse_to_csv(
                html,
                staging / task.csv_filename,
                debug_dir / task.html_filename
                if debug and not use_local_html
                else None,
                task.columns,
            )
            if task.key:
                read_csv_rows(
                    staging / task.csv_filename,
                    task.columns,
                    key=task.key,
                    prefix=task.prefix,
                )
        metadata = json.dumps(manifest, indent=2) + "\n"
        (staging / SUPPLEMENT_MANIFEST).write_text(metadata, encoding="utf-8")
        if debug and not use_local_html:
            (debug_dir / SUPPLEMENT_MANIFEST).write_text(metadata, encoding="utf-8")
        yield staging
    finally:
        if (csv_dir / CSV_REFRESH_MARKER).exists():
            logger.warning("Incomplete refresh; retaining staging files at %s", staging)
        else:
            temporary.cleanup()


def download_tasks() -> tuple[DownloadTable, ...]:
    """Fetch only native join identifiers and fields missing from stare models.

    API data owns statuses, people roles, review dates, affiliations, titles
    exposed by the API and publication links. CONF notes need no supplement.
    Current Paper Draft has no dedicated API field; keep the export rather
    than guessing which supporting-document label denotes the current draft.
    """
    return (
        DownloadTable(
            "analyses",
            http.URLS["analyses"],
            ("Reference Code", "Internal Note Editors"),
            "reference_code",
            key="Reference Code",
            prefix="ANA-",
        ),
        DownloadTable(
            "papers",
            http.URLS["papers"],
            ("Reference Code", "Figures", "Current Paper Draft"),
            "reference_code",
            key="Reference Code",
        ),
        DownloadTable(
            "pubnotes",
            http.URLS["pubnotes"],
            ("Temporary Reference Code", "Reference Code"),
            "final_ref_code",
            key="Temporary Reference Code",
            prefix="PUB-",
        ),
    )
