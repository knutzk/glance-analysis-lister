# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""A progressively enhanced table of independent, prepared publications."""

from html import escape

from ..people import board_names
from .fragments import affiliation_tags, fields
from .layout import metadata_json, readable_html
from .links import anchor, glance_url, html_link
from .publication_controls import render_controls


def paper_details(row):
    groups = dict(row.details.groups)
    groups["leadingSubgroup"] = row.metadata["leading_subgroup"]
    groups["subgroups"] = list(row.subgroups)
    out = affiliation_tags(groups)
    if any(
        "inherited" in row.provenance[key]["reason"]
        for key in ("subgroups", "leading_subgroup")
    ):
        out += '<p class="gal-affiliation-source">Via linked analysis</p>'
    out += '<div class="gal-publication-details__columns"><div>'
    milestone = row.details.last_milestone
    status = f"{milestone[0]} · {milestone[1]}" if milestone else row.state
    out += fields(
        [
            ("Paper status", status),
            ("Analysis contacts", ", ".join(row.details.contacts)),
            ("Contact editors", ", ".join(row.details.editors)),
            (
                "Editorial board",
                ", ".join(board_names(row.details.board, row.details.board_chairs)),
            ),
        ]
    )
    out += "</div><div>"
    for label, key in (
        ("Keywords", "keywords"),
        ("Triggers", "triggers"),
        ("Statistical tools", "statistical_tools"),
    ):
        out += f'<p class="gal-card__label">{label}</p>'
        out += (
            '<div class="gal-publication-tags">'
            + "".join(
                f'<span class="gal-badge">{escape(value)}</span>\n'
                for value in row.metadata[key]
            )
            + "</div>"
            if row.metadata[key]
            else "<p>Not recorded</p>"
        )
    links = [
        link
        for link in row.details.links
        if link.url not in {item.url for item in row.details.publication_records}
    ]
    if links:
        out += '<p class="gal-card__label">Supporting links</p><ul>'
        for link in links:
            label, url = link.label, link.url
            prefix = escape(label) + ": " if label and label != url else ""
            out += f"<li>{prefix}{html_link(url, url)}</li>"
        out += "</ul>"
    return out + "</div></div>"


def record_button(label, url):
    return html_link(label, url).replace("<a ", '<a class="gal-publication-link" ', 1)


def paper_table(view):
    resource = "papers"
    rows = tuple(row for row in view.archive if row.resource == resource)
    out = '<section class="gal-collection gal-archive" data-gal-archive data-gal-collection data-gal-noun="papers" aria-label="Papers archive">'
    out += render_controls(
        anchor(view.profile.group, "papers-filters"),
        "Search papers",
        "Identifier, subgroup, title, citation, DOI, keyword or person",
        [
            (
                "publication_status",
                "Publication status",
                view.controls[resource]["publication_status"],
            )
        ],
    )
    out += f'<p class="gal-result-count" data-gal-count role="status" aria-live="polite" aria-atomic="true">{len(rows)} papers</p>'
    out += '<div class="gal-table-scroll" role="region" aria-label="Publication archive table" tabindex="0"><table class="gal-papers">\n<thead>\n<tr>'
    out += "".join(
        f'<th scope="col">{label}</th>'
        for label in ("Identifier", "Title", "Publication record", "Publication date")
    )
    out += "</tr>\n</thead>\n<tbody>\n"
    for row in rows:
        identifier = anchor(
            view.profile.group, row.reference, kind="publication-papers"
        )
        metadata = metadata_json(
            {key: row.metadata[key] for key in ("text", "publication_status")}
        )
        out += f'<tr id="{identifier}" data-gal-item data-gal-date="{row.date or ""}" data-gal-metadata="{metadata}"><th scope="row">{record_button(row.label, glance_url("papers", row.reference))}</th>'
        out += f'<td><span data-gal-paper-toggle aria-controls="{identifier}-details">{escape(row.title)}</span></td><td><div class="gal-publication-records">'
        out += "".join(
            record_button(item.label, item.url)
            for item in row.details.publication_records
        )
        out += "</div></td><td>"
        if row.date:
            out += f'<time datetime="{row.date}">{row.date}</time>'
        out += f'</td></tr>\n<tr class="gal-paper-detail-row" id="{identifier}-details" data-gal-paper-details><td colspan="4"><div class="gal-publication-details__body">'
        out += paper_details(row)
        out += f'<div class="gal-paper-collapse-row"><button type="button" data-gal-paper-collapse aria-controls="{identifier}-details" hidden>Collapse <span aria-hidden="true">▴</span></button></div></div></td></tr>\n'
    out += "</tbody>\n</table></div>"
    out += '<p class="gal-no-results" data-gal-empty hidden>No papers match these filters. Reset the filters to see the full paper archive.</p>'
    return readable_html(out + "</section>") + "\n"
