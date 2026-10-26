# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Read HTML-derived CSVs with strict headers, identifiers and row validation."""

import csv
import re
from collections import Counter
from pathlib import Path


def read_csv_rows(
    path: Path, required_columns=(), *, key=None, prefix=""
) -> list[dict[str, str]]:
    """Return the rows of one CSV file.

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
            f"{path} not found. Re-run analysis-lister download-html."
        ) from None

    if not rows:
        raise ValueError(
            f"{path} holds no rows. GLANCE probably returned a login page; "
            "renew the cookies and re-run analysis-lister download-html."
        )

    return rows
