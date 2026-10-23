# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Accessible HTML cards and progressive filter controls for prepared analyses."""

import json
from html import escape

from .fragments import affiliation_tags, fields
from .links import anchor, glance_url, html_link
from .ongoing_controls import active_subgroup_buttons, render_controls


def analysis_card(row, group):
    metadata = {
        **row.filter_metadata,
        "reference": row.reference,
    }
    encoded = escape(json.dumps(metadata, ensure_ascii=False), quote=True)
    identifier = anchor(group, row.reference)
    heading = identifier + "-title"
    out = f'<article class="gal-card" id="{identifier}" aria-labelledby="{heading}" data-gal-item data-gal-metadata="{encoded}">\n'
    out += '<header class="gal-card__header"><div class="gal-card__title-line">'
    out += '<span class="gal-card__glance-links">'
    out += f'<a class="gal-glance-button" href="{escape(glance_url("analyses", row.reference), quote=True)}" aria-label="GLANCE analysis {escape(row.reference, quote=True)}">{escape(row.reference)}</a>'
    for link in row.publications:
        if link["resource"] in {"papers", "confnotes", "pubnotes"} and (
            link["resource"] != "papers" or row.stage == "publication_review"
        ):
            kind = {
                "papers": "Paper",
                "confnotes": "CONF note",
                "pubnotes": "PUB note",
            }[link["resource"]]
            label = link["reference"] if link["resource"] == "papers" else kind
            out += f'<a class="gal-glance-button" href="{escape(glance_url(link["resource"], link["reference"]), quote=True)}" aria-label="GLANCE {kind}: {escape(link["reference"], quote=True)}" title="{escape(link["reference"], quote=True)}">{escape(label)}</a>'
    out += "</span>"
    out += f'<h2 id="{heading}"><span data-gal-card-toggle aria-controls="{identifier}-details">{escape(row.title)}</span></h2>'
    out += "</div>"
    out += affiliation_tags(row.groups)
    out += '<div class="gal-card__actions">'
    out += f'<a class="gal-card__permalink" href="#{identifier}" aria-label="Link to {escape(row.reference, quote=True)}" title="Link to this analysis">#</a>'
    out += "</div></header>"
    out += '<ol class="gal-progress" aria-label="Approval milestones">'
    flow_labels = {
        "EdBoard assignment": "EdBoard",
        "Pre-approval sign-off": "Pre-approval",
        "Approval sign-off": "Approval",
        "ATLAS circulation 1": "1st circulation",
        "ATLAS circulation 2": "2nd circulation",
    }
    for step in row.progress:
        state = "Recorded" if step["reached"] else "Not recorded"
        detail = step["date"] or (
            "In progress"
            if step["reached"] and step["label"] == "Publication review"
            else state
        )
        out += f'<li class="gal-progress__step{" gal-progress__step--reached" if step["reached"] else ""}" title="{escape(detail, quote=True)}"><span class="gal-progress__marker" aria-hidden="true">{"✓" if step["reached"] else "○"}</span><strong>{escape(flow_labels.get(step["label"], step["label"]))}</strong><span class="gal-visually-hidden">: {escape(detail)}</span></li>'
    out += f'</ol><div class="gal-card__details" id="{identifier}-details"><div class="gal-card__columns"><div>'
    out += fields(
        [
            (
                "Last phase-0 milestone",
                f"{row.milestone[0]} · {row.milestone[1]}" if row.milestone else "",
            ),
            *[
                (
                    "Last paper milestone (" + paper["reference"] + ")",
                    f"{paper['milestone']['value'][0]} · {paper['milestone']['value'][1]}"
                    if paper["milestone"]["value"]
                    else "",
                )
                for paper in row.paper_milestones
            ],
            ("Analysis contacts", ", ".join(row.contacts)),
            ("Internal-note editors", ", ".join(row.internal_editors)),
            ("Contact editors", ", ".join(row.editors)),
            (
                "Editorial board",
                ", ".join(
                    name + (" (chair)" if name in row.board_chairs else "")
                    for name in dict.fromkeys([*row.board, *row.board_chairs])
                ),
            ),
        ]
    )
    out += "</div><div>"
    if row.email_lists:
        out += '<p class="gal-card__label">Email lists</p><ul>'
        for item in row.email_lists:
            out += f'<li><a href="mailto:{escape(item["address"], quote=True)}">{escape(item["address"])}</a></li>'
        out += "</ul>"
    if row.documents:
        out += '<p class="gal-card__label">Supporting documents</p><ul>'
        for doc in row.documents:
            url = doc.get("url") or ""
            label = doc.get("label") or "Document"
            prefix = "" if label == url else escape(label) + ": "
            out += f"<li>{prefix}{html_link(url, url)}</li>"
        out += "</ul>"
    for label, values in (
        ("Statistical tools", metadata["statistical_tools"]),
        ("Triggers", metadata["triggers"]),
        ("Keywords", row.keywords),
    ):
        if values:
            out += f'<p class="gal-card__label">{label}</p><div class="gal-card__keyword-tags">'
            out += "".join(
                f'<span class="gal-badge">{escape(value)}</span>' for value in values
            )
            out += "</div>"
    return (
        out
        + f'</div></div><div class="gal-card__collapse-row"><button type="button" class="gal-card__collapse" data-gal-card-collapse aria-controls="{identifier}-details" hidden>Collapse <span aria-hidden="true">▴</span></button></div></div></article>\n'
    )


def filter_controls(rows, group, subgroup_buttons):
    prefix = anchor(group, "filters")
    return render_controls(
        prefix,
        "Search analyses",
        "Identifier, title, people, keywords or triggers",
        [("subgroups", "Subgroups", active_subgroup_buttons(rows, subgroup_buttons))],
        sort_options=[
            ("stage-desc", "Review stage: most advanced first"),
            ("stage-asc", "Review stage: earliest first"),
            ("reference", "Analysis identifier"),
        ],
    )


def ongoing_cards(view):
    out = '<section class="gal-collection gal-ongoing" data-gal-collection data-gal-noun="analyses" aria-label="Ongoing analyses">\n'
    out += filter_controls(view.ongoing, view.profile.group, view.subgroup_buttons)
    out += f'<p class="gal-result-count" data-gal-count role="status" aria-live="polite" aria-atomic="true">{len(view.ongoing)} analyses</p>\n'
    out += (
        '<div class="gal-cards">\n'
        + "".join(analysis_card(row, view.profile.group) for row in view.ongoing)
        + "</div>\n"
    )
    out += '<p class="gal-no-results" data-gal-empty hidden>No analyses match these filters. Reset the filters to see all analyses.</p>\n'
    return out + "</section>\n\n"
