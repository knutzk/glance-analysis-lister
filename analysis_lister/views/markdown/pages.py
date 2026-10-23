# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Ongoing analyses, rendered without selection or file I/O."""

from .cards import ongoing_cards
from .formatting import text
from .links import external, glance_url


def provenance(view):
    fetched = text(view.source_metadata.get("fetched_at") or "unknown")
    built = text(
        (view.source_metadata.get("gal_curation") or {}).get("built_at") or "unknown"
    )
    return (
        "---\n\n"
        f'API snapshot: <code class="gal-snapshot-date">{fetched}</code>. '
        f'Curated registry built: <code class="gal-snapshot-date">{built}</code>.\n\n'
        "Derivation rules and source evidence: [view report](view-report.json).\n\n"
    )


def ongoing_page(view):
    out = "---\nhide:\n  - toc\n---\n\n"
    out += f"# {text(view.profile.title)} ongoing analyses\n\n"
    out += "Includes analyses with leading or additional group participation that are in active phase 0 or have an explicitly linked publication under review. "
    out += "Completed and closed analyses are excluded; uncertain entries are listed at the bottom. "
    out += "Each analysis appears once.\n\nClick a collapsed card for more information and links; use Collapse at the bottom to close it. The GLANCE buttons open the analysis or publication entry directly.\n\n"
    if view.ongoing:
        out += ongoing_cards(view)
    else:
        out += "No analyses currently meet the ongoing selection rules.\n\n"
    if view.needs_review:
        out += '<a id="needs-review"></a>\n\n## Needs review\n\n'
        out += "These affiliated analyses cannot be classified confidently and are excluded from the ongoing total. See the view report for evidence.\n\n"
        for row in view.needs_review:
            out += f"- {external(row.reference, glance_url('analyses', row.reference))} – {text(row.title)}\n"
        out += "\n"
    return out + provenance(view)
