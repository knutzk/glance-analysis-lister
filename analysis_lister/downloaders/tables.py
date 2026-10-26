# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Parse GLANCE HTML tables without reading or writing files."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import Tag

logger = logging.getLogger(__name__)


def parse_html_table(html: str, *, source: str) -> Tag:
    """Repair GLANCE's missing cell end tags and extract the first table."""
    from bs4 import BeautifulSoup

    malformed_td_pattern = r"(<td>.*?)(?=<td>)"
    fixed_html = re.sub(malformed_td_pattern, r"\1</td>", html, flags=re.DOTALL)
    fixed_html = fixed_html.replace("\n", " ")
    table = BeautifulSoup(fixed_html, "html.parser").find("table")
    if table is None:
        raise ValueError(f"No table found for {source}")
    return table


def table_to_rows(table: Tag, *, source: str) -> list[list[str]]:
    """Validate and return every CSV column in source order, including headers.

    Keep data cells unchanged. The source label is used in diagnostics only;
    this function never opens it as a path.
    """
    rows = table.find_all("tr")
    if not rows:
        raise ValueError(f"No rows in table for {source}")

    headers = [th.text.strip() for th in rows[0].find_all("th")]
    ambiguous = [
        name
        for name, count in Counter(headers).items()
        if count > 1 and name in {"Reference Code", "Temporary Reference Code"}
    ]
    if not headers:
        raise ValueError(f"Invalid table headers for {source}: no header cells")
    if ambiguous:
        raise ValueError(
            f"Invalid table headers for {source}: ambiguous columns={ambiguous}"
        )
    header_indices = dict(enumerate(headers))

    # Full exports may contain distinct columns with identical display labels.
    # Keep their positions and values, reserving all native names so a generated
    # suffix cannot collide with another source column.
    reserved, used = set(header_indices.values()), set()
    for index, header in header_indices.items():
        base = header or f"Unnamed column {index + 1}"
        name = base
        if name in used or (not header and name in reserved):
            suffix = 2
            name = f"{base} ({suffix})"
            while name in reserved or name in used:
                suffix += 1
                name = f"{base} ({suffix})"
        used.add(name)
        if name != header:
            logger.warning(
                "%s: %s HTML header %r at column %d exported as %r; all columns retained",
                source,
                "duplicate" if header else "unnamed",
                header,
                index + 1,
                name,
            )
            header_indices[index] = name
    csv_data = [list(header_indices.values())]

    for row_number, row in enumerate(rows[1:], start=2):
        cells = row.find_all("td")
        if not cells:
            continue

        if len(cells) != len(headers):
            raise ValueError(
                f"{source}: table row {row_number}: expected {len(headers)} "
                f"cells, found {len(cells)}; cannot safely align the columns"
            )
        csv_data.append([cells[idx].text for idx in header_indices])

    if len(csv_data) == 1:
        raise ValueError(f"No data rows in table for {source}")

    return csv_data


def validate_table_completeness(table: Tag, row_count: int, *, source: str) -> None:
    """Reject missing counters, partial pages, and truncated table responses.

    GLANCE reports 'Showing 1 to N of N results' outside the result table.
    Only that explicit counter establishes completeness; comments, record
    titles and script text must not be mistaken for pagination metadata.
    """
    document = table
    while document.parent is not None:
        document = document.parent
    number = r"(?:\d{1,3}(?:[, \u00a0\u202f]\d{3})+|\d+)"
    counter = re.compile(
        rf"Showing\s+({number})\s+to\s+({number})\s+of\s+({number})\s+results",
        re.IGNORECASE,
    )
    counts = set()
    for node in document.find_all(string=counter):
        if node.find_parent(["table", "script", "style"]):
            continue
        match = counter.fullmatch(" ".join(node.split()))
        if match is not None:
            counts.add(
                tuple(
                    int(value.replace(",", "").replace(" ", ""))
                    for value in match.groups()
                )
            )
    if len(counts) != 1:
        raise ValueError(
            f"{source}: missing or conflicting GLANCE result counters; "
            "download completeness cannot be verified"
        )
    first, last, total = counts.pop()
    if first != 1 or last != total or row_count != total:
        raise ValueError(
            f"{source}: incomplete GLANCE table: parsed {row_count} rows, "
            f"server reports {first} to {last} of {total} results. "
            "Paginated or truncated responses are not published."
        )
