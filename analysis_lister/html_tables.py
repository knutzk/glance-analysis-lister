# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Parse GLANCE HTML tables without reading or writing files."""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Sequence
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


def table_to_rows(
    table: Tag, *, source: str, column_filter: Sequence[str] | None = None
) -> list[list[str]]:
    """Validate a table and return selected CSV rows, including the header.

    Keep data cells unchanged and columns in source order. The source label is
    used in diagnostics only; this function never opens it as a path.
    """
    rows = table.find_all("tr")
    if not rows:
        raise ValueError(f"No rows in table for {source}")

    headers = [th.text.strip() for th in rows[0].find_all("th")]
    selected = [h for h in headers if not column_filter or h in column_filter]
    duplicates = [h for h, n in Counter(selected).items() if n > 1]
    if not headers or any(not h for h in selected) or duplicates:
        raise ValueError(f"Invalid table headers for {source}: duplicates={duplicates}")

    # Filter headers based on the column_filter, otherwise include all.
    if column_filter:
        # A column that GLANCE has renamed would silently turn into an
        # empty field for every single entry, so stop right here.
        missing = sorted({col for col in column_filter if col not in headers})
        if missing:
            logger.error(
                f"Columns missing from the table for {source}: {missing}. "
                "GLANCE has probably renamed them; update the field maps in "
                "analysis_lister/glance/field_maps.py."
            )
            raise ValueError(f"Missing columns for {source}: {missing}")

        header_indices = {
            index: header
            for index, header in enumerate(headers)
            if header in column_filter
        }
        logger.info(f"Filtering columns: {list(header_indices.values())}")
    else:
        header_indices = dict(enumerate(headers))

    csv_data = [[header_indices[idx] for idx in header_indices]]

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
