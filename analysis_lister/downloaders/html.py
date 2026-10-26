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

from attrs import frozen

from analysis_lister.downloaders.csv_io import read_csv_rows
from analysis_lister.downloaders.tables import (
    parse_html_table,
    table_to_rows,
    validate_table_completeness,
)

from . import http
from .manifest import CSV_REFRESH_MARKER, HTML_MANIFEST, make_manifest, read_manifest

logger = logging.getLogger(__name__)


class HTMLParser:
    @staticmethod
    def parse_to_csv(
        html: str,
        output_csv: Path,
        debug_path: Path | None = None,
    ) -> int:
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

        csv_data = table_to_rows(table, source=source)
        validate_table_completeness(table, len(csv_data) - 1, source=source)
        with output_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)
        logger.debug("CSV file successfully generated: %s", output_csv)
        logger.info("%s: %s rows; complete", output_csv.stem, f"{len(csv_data) - 1:,}")
        return len(csv_data) - 1


@frozen
class DownloadTable:
    """GLANCE table metadata; destinations are supplied to the workflow separately."""

    name: str
    url: str
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
) -> Iterator[tuple[Path, dict[str, int]]]:
    """Yield a complete CSV batch without modifying the current data."""
    if debug and not use_local_html and debug_dir.resolve() == csv_dir.resolve():
        raise ValueError("Saved HTML and CSV output must use separate directories")
    if (
        any((csv_dir / task.csv_filename).exists() for task in tasks)
        or (csv_dir / HTML_MANIFEST).exists()
    ):
        read_manifest(csv_dir, tasks)
    manifest = (
        read_manifest(debug_dir, tasks) if use_local_html else make_manifest(tasks)
    )
    csv_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so individual replacements are atomic.
    temporary = TemporaryDirectory(prefix=".refresh-", dir=csv_dir, delete=False)
    staging = Path(temporary.name)
    counts = {}
    try:
        if debug and not use_local_html:
            (debug_dir / HTML_MANIFEST).unlink(missing_ok=True)
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
            counts[task.name] = HTMLParser.parse_to_csv(
                html,
                staging / task.csv_filename,
                debug_dir / task.html_filename
                if debug and not use_local_html
                else None,
            )
            if task.key:
                read_csv_rows(
                    staging / task.csv_filename,
                    (task.key,),
                    key=task.key,
                    prefix=task.prefix,
                )
        metadata = json.dumps(manifest, indent=2) + "\n"
        (staging / HTML_MANIFEST).write_text(metadata, encoding="utf-8")
        if debug and not use_local_html:
            (debug_dir / HTML_MANIFEST).write_text(metadata, encoding="utf-8")
        yield staging, counts
    finally:
        if (csv_dir / CSV_REFRESH_MARKER).exists():
            logger.warning("Incomplete refresh; retaining staging files at %s", staging)
        else:
            temporary.cleanup()


def download_tasks() -> tuple[DownloadTable, ...]:
    """Export all available columns from all four GLANCE HTML resource tables."""
    return tuple(
        DownloadTable(
            name,
            http.URLS[name],
            "final_ref_code" if name in {"confnotes", "pubnotes"} else "reference_code",
            key="Temporary Reference Code"
            if name in {"confnotes", "pubnotes"}
            else "Reference Code",
            prefix={"analyses": "ANA-", "confnotes": "CONF-", "pubnotes": "PUB-"}.get(
                name, ""
            ),
        )
        for name in ("analyses", "papers", "confnotes", "pubnotes")
    )
