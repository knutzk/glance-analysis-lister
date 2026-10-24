# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publication pages and ongoing analyses, rendered without selection or file I/O."""

import re

from ..curation import archive_curation_statement
from .formatting import text
from .links import external, glance_url
from .notes import note_table
from .ongoing import ongoing_cards
from .papers import paper_table


def archive_curation_intro(view):
    out = '<aside class="gal-archive-scope" aria-label="Archive scope">\n'
    out += (
        f"<p>This archive is not limited to publications spearheaded by <strong>{text(view.profile.group)}</strong>. "
        "It also includes work led by other groups that matches the criteria below.</p>\n"
    )
    out += f"<p>{text(archive_curation_statement(view.profile))}</p>\n"
    policy = view.profile.publication_policy
    criteria = []
    for label, values in (
        ("Groups", policy.groups if policy else ()),
        ("Subgroups", policy.subgroups if policy else ()),
        ("Keywords", policy.keywords if policy else ()),
    ):
        if values:
            criteria.append(
                f"<div><dt>{label}</dt><dd>"
                + ", ".join("<code>" + text(value) + "</code>" for value in values)
                + "</dd></div>"
            )
    if criteria:
        out += "<dl>" + "\n".join(criteria) + "</dl>\n"
    return out + "</aside>\n\n"


def provenance(view, revision=None):
    fetched = text(view.source_metadata.get("fetched_at") or "unknown")
    repository = "https://github.com/knutzk/glance-analysis-lister"
    generator = f"Generated with [glance-analysis-lister]({repository})"
    if revision and re.fullmatch(r"[0-9a-f]{40}(?:-dirty)?", revision):
        commit = revision.removesuffix("-dirty")
        generator += f", commit [`{commit[:12]}`]({repository}/commit/{commit})"
        if revision.endswith("-dirty"):
            generator += " (modified checkout)"
    return (
        "---\n\n"
        f'GLANCE data extracted: <code class="gal-snapshot-date">{fetched}</code>. '
        + generator
        + ".\n\n"
    )


def ongoing_page(view, *, revision=None):
    out = "---\nhide:\n  - toc\n---\n\n"
    out += f"# {text(view.profile.title)} ongoing analyses\n\n"
    out += "Includes analyses with leading or additional group participation that are in active phase 0, have an explicitly linked publication under review, or have finished phase 0 and are awaiting review of a linked publication marked Created. "
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
    return out + provenance(view, revision)


def publication_page(view, resource, *, revision=None):
    labels = {"papers": "Papers", "confnotes": "CONF notes", "pubnotes": "PUB notes"}
    label = labels[resource]
    out = "---\nhide:\n  - toc\n---\n\n"
    out += f"# {text(view.profile.publication_title)} {label.lower()}\n\n"
    out += archive_curation_intro(view)
    out += (
        "Submitted and published papers across all available years. "
        if resource == "papers"
        else "Released notes across all available years, including superseded historical notes. "
    )
    out += (
        "Dates are paper publication dates.\n\n"
        if resource == "papers"
        else "Dates are note release dates.\n\n"
    )
    return out + paper_table(view) + provenance(view, revision)


def papers_page(view, *, revision=None):
    return publication_page(view, "papers", revision=revision)


def confnotes_page(view, *, revision=None):
    out = "---\nhide:\n  - toc\n---\n\n"
    out += f"# {text(view.profile.publication_title)} CONF notes\n\n"
    out += archive_curation_intro(view)
    out += "Superseded notes are hidden by default.\n\n"
    return out + note_table(view, "confnotes") + provenance(view, revision)


def pubnotes_page(view, *, revision=None):
    out = "---\nhide:\n  - toc\n---\n\n"
    out += f"# {text(view.profile.publication_title)} PUB notes\n\n"
    out += archive_curation_intro(view)
    out += "Superseded notes are hidden by default.\n\n"
    return out + note_table(view, "pubnotes") + provenance(view, revision)
