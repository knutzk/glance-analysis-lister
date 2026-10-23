# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared compact CONF/PUB-note tables, details and subgroup-involvement controls."""

import json
import re
from html import escape

from ...registry.reader import LINK_RESOURCES
from .cards import affiliation_tags, fields
from .links import anchor, glance_url, html_link
from .publication_filtering import date_controls, expansion_control, search_control


def note_details(row):
    groups = dict(row.details["groups"])
    groups["leadingSubgroup"] = row.filter_metadata["leading_subgroup"]
    groups["subgroups"] = list(row.subgroups)
    extra = row.details["conf_note" if row.resource == "confnotes" else "pub_note"]
    out = affiliation_tags(groups)
    if (
        "inherited" in row.provenance["subgroups"]["reason"]
        or "inherited" in row.provenance["leading_subgroup"]["reason"]
    ):
        out += '<p class="gal-card__label">Subgroup assignments via linked analysis</p>'
    if extra["superseded"]:
        out += '<p class="gal-card__label">Superseded by</p><ul class="gal-confnote-superseders">'
        for link in extra["superseded_by"]:
            kind = link.get("type") or "Publication"
            reference = link.get("referenceCode") or "Not recorded"
            resource = LINK_RESOURCES.get(kind)
            label = str(kind) + ": " + str(reference)
            out += (
                "<li>"
                + (
                    html_link(label, glance_url(resource, reference))
                    if resource and link.get("referenceCode")
                    else escape(label)
                )
                + "</li>"
            )
        out += "</ul>"
    out += '<div class="gal-confnote-details__columns"><div>'
    out += fields(
        [(person["label"], ", ".join(person["names"])) for person in extra["people"]]
    )
    out += "</div><div>"
    tags = [
        {"label": label, "values": row.filter_metadata[key]}
        for label, key in (
            ("Keywords", "keywords"),
            ("Triggers", "triggers"),
            ("Statistical tools", "statistical_tools"),
        )
    ] + extra["tags"]
    for category in tags:
        out += f'<p class="gal-card__label">{escape(category["label"])}</p>'
        if category["values"]:
            out += (
                '<div class="gal-confnote-tags">'
                + "".join(
                    f'<span class="gal-badge">{escape(value)}</span>'
                    for value in category["values"]
                )
                + "</div>"
            )
        else:
            out += "<p>Not recorded</p>"
    relation = extra["related_analysis"] or {}
    if relation.get("type") == "Analysis" and relation.get("referenceCode"):
        reference = relation["referenceCode"]
        out += (
            "<p>Analysis: "
            + html_link(reference, glance_url("analyses", reference))
            + "</p>"
        )
    if row.details["links"]:
        out += '<p class="gal-card__label">Supporting links</p><ul>'
        for link in row.details["links"]:
            url = link.get("url") or ""
            label = link.get("label") or ""
            prefix = escape(label) + ": " if label and label != url else ""
            out += f"<li>{prefix}{html_link(url, url)}</li>"
        out += "</ul>"
    out += "</div></div>"
    return out


def note_table(view, resource):
    if resource not in {"confnotes", "pubnotes"}:
        raise ValueError("Note tables support CONF notes and PUB notes")
    kind = "CONF" if resource == "confnotes" else "PUB"
    public_prefix = "ATLAS-CONF" if resource == "confnotes" else "ATL-PHYS-PUB"
    rows = tuple(row for row in view.archive if row.resource == resource)
    out = f'<section class="gal-collection gal-archive gal-confnote-collection" data-gal-resource="{resource}" data-gal-confnotes aria-label="{kind} notes">'
    out += '<div class="gal-filters gal-confnote-filters" data-gal-confnote-controls hidden><div class="gal-confnote-filter-groups">'
    out += search_control(
        anchor(view.profile.group, resource + "-filters"),
        f"Search {kind} notes",
        "Identifier, subgroup, title, citation, CDS URL, keyword or person",
    )
    out += date_controls(anchor(view.profile.group, resource + "-dates"), release=True)
    out += '<div class="gal-publication-filter-row"><fieldset data-gal-confnote-status><legend>Supersession</legend><div class="gal-filter-buttons"><button type="button" data-gal-confnote-supersession="non-superseded" aria-pressed="true">Non-superseded</button><button type="button" data-gal-confnote-supersession="superseded" aria-pressed="false">Superseded</button></div></fieldset>'
    out += '<div class="gal-filter-actions">' + expansion_control()
    out += '<button type="button" data-gal-confnote-reset>Reset filters</button></div></div></div></div>'
    out += f'<p class="gal-result-count" data-gal-confnote-count role="status" aria-live="polite" aria-atomic="true">{len(rows)} of {len(rows)} notes</p>'
    out += f'<div class="gal-table-scroll" role="region" aria-label="{kind} notes table" tabindex="0"><table class="gal-confnotes"><thead><tr>'
    for label in ("Identifier", "Title", "Release date"):
        out += f'<th scope="col">{label}</th>'
    out += "</tr></thead><tbody>"
    for row in rows:
        if not re.fullmatch(re.escape(public_prefix) + r"-\d{4}-\d+", row.label):
            raise ValueError(
                f"Released {kind} note must have a {public_prefix} identifier"
            )
        identifier = anchor(
            view.profile.group,
            row.reference,
            kind="confnote" if resource == "confnotes" else "pubnote",
        )
        subgroups = escape(
            json.dumps(row.filter_metadata["subgroups"], ensure_ascii=False), quote=True
        )
        superseded = (
            "true"
            if row.details["conf_note" if resource == "confnotes" else "pub_note"][
                "superseded"
            ]
            else "false"
        )
        out += f'<tr id="{identifier}" data-gal-confnote data-gal-search-text="{escape(row.filter_metadata["text"], quote=True)}" data-gal-date="{row.date or ""}" data-gal-subgroups="{subgroups}" data-gal-superseded="{superseded}">'
        out += f'<th scope="row"><div class="gal-confnote-links"><a class="gal-confnote-link" href="{escape(glance_url(resource, row.reference), quote=True)}" aria-label="GLANCE entry for {escape(row.label, quote=True)}">{escape(row.label)}</a>'
        cds_url = row.details.get("cds_url")
        if cds_url:
            out += html_link("CDS", cds_url).replace(
                "<a ", '<a class="gal-confnote-link" ', 1
            )
        out += f'</div></th><td><span data-gal-confnote-toggle aria-controls="{identifier}-details">{escape(row.title)}</span></td><td>'
        if row.date:
            out += f'<time datetime="{row.date}">{row.date}</time>'
        out += "</td></tr>"
        out += f'<tr class="gal-confnote-detail-row" id="{identifier}-details" data-gal-confnote-details><td colspan="3"><div class="gal-confnote-details">'
        out += note_details(row)
        out += f'<div class="gal-confnote-collapse-row"><button type="button" data-gal-confnote-collapse aria-controls="{identifier}-details" hidden>Collapse <span aria-hidden="true">▴</span></button></div></div></td></tr>'
    out += f"</tbody></table></div><p data-gal-confnotes-empty hidden>No {kind} notes match the selected filters.</p>"
    return out + "</section>\n\n"
