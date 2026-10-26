# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Reusable HTML people fields and affiliation tags."""

from html import escape


def fields(items, *, missing="Not recorded"):
    return (
        '<dl class="gal-card__fields">'
        + "".join(
            f"<dt>{escape(label)}</dt><dd>{escape(value or missing)}</dd>"
            for label, value in items
        )
        + "</dl>"
    )


def affiliation_tags(groups):
    out = ""
    out += '<div class="gal-card__affiliations" aria-label="Groups and subgroups in the current snapshot">'
    for names, leading, kind in (
        (
            [groups.get("leadingGroup"), *(groups.get("otherGroups") or [])],
            groups.get("leadingGroup"),
            "group",
        ),
        (
            [groups.get("leadingSubgroup"), *(groups.get("subgroups") or [])],
            groups.get("leadingSubgroup"),
            "subgroup",
        ),
    ):
        if kind == "subgroup":
            out += '<span class="gal-card__divider" aria-hidden="true">|</span>'
        out += f'<span class="gal-card__tagset" aria-label="{kind.capitalize()}s">'
        for name in dict.fromkeys(name for name in names if name):
            lead = name == leading
            out += f'<span class="gal-badge{" gal-badge--leading" if lead else ""}">{escape(name)}<span class="gal-visually-hidden"> ({"leading" if lead else "additional"} {kind})</span></span>\n'
        out += "</span>"
    return out + "</div>"
