# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stable source layout for the controlled HTML emitted by the renderers."""

import json
import re
from html import escape


def metadata_json(values):
    """Keep each filter field on its own line, with stable property ordering."""
    return escape(
        "{\n"
        + ",\n".join(
            "  "
            + json.dumps(key)
            + ": "
            + json.dumps(values[key], ensure_ascii=False, sort_keys=True)
            for key in sorted(values)
        )
        + "\n}",
        quote=True,
    )


def readable_html(source):
    """Separate blocks and fields, preserving compact rows and inline content.

    Source values have already been escaped. This only lays out our own markup;
    it does not parse or reserialize attributes, text, or inline HTML. Keep blank
    lines out of the result so Markdown continues treating it as one HTML block.
    """
    rows = []

    def keep_row(match):
        row = match.group()
        if re.search(r'class="gal-(?:paper|note)-detail-row"', row):
            return row
        token = f"<!--gal-compact-row-{len(rows)}-->"
        rows.append(row)
        return "\n" + token + "\n"

    source = re.sub(r"<tr\b[^>]*>.*?</tr>", keep_row, source, flags=re.DOTALL)
    source = re.sub(
        r"</?(?:section|article|header|div|ol|ul|dl|table|thead|tbody|tr|td|fieldset|select)\b[^>]*>",
        lambda match: "\n" + match.group() + "\n",
        source,
    )
    source = re.sub(
        r"<(p|li|h2)\b[^>]*>.*?</\1>|<dt\b[^>]*>.*?</dt><dd\b[^>]*>.*?</dd>",
        lambda match: "\n" + match.group() + "\n",
        source,
        flags=re.DOTALL,
    )
    source = "\n".join(line for line in source.splitlines() if line.strip())
    for index, row in enumerate(rows):
        source = source.replace(f"<!--gal-compact-row-{index}-->", row)
    # Metadata changes should not replace the visible cells in the same diff line.
    source = re.sub(
        r' (data-gal-(?:metadata|search-text|subgroups)="[^"]*")', r"\n  \1", source
    )
    source = re.sub(r"(<tr\b[^>]*>)", r"\1\n", source)
    return "\n".join(line for line in source.splitlines() if line.strip()) + "\n"
