# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Stable local anchors and links to native GLANCE resources."""

import re
from html import escape
from urllib.parse import quote, urlencode, urlsplit

from .formatting import text


def anchor(group, reference, *, kind="analysis"):
    return (
        kind
        + "-"
        + re.sub(r"[^a-z0-9-]+", "-", (group + "-" + reference).lower()).strip("-")
    )


def glance_url(resource, reference):
    return (
        f"https://atlas-glance.cern.ch/atlas/analysis/{resource}/details.php?"
        + urlencode({"ref_code": reference})
    )


def external(label, url):
    try:
        allowed = isinstance(url, str) and urlsplit(url).scheme.lower() in {
            "https",
            "http",
        }
    except ValueError:
        allowed = False
    if not allowed:
        return text(label)
    return f"[{text(label)}](<{quote(url, safe=':/?=&%#@+;,~!$*-._')}>)"


def html_link(label, url):
    """Render an escaped HTTP(S) link inside raw HTML collections."""
    try:
        allowed = isinstance(url, str) and urlsplit(url).scheme in {"http", "https"}
    except ValueError:
        allowed = False
    label = escape(str(label or ""))
    return f'<a href="{escape(url, quote=True)}">{label}</a>' if allowed else label
