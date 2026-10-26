# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Native, progressive filter controls shared by cards and tables."""

from html import escape

from .controls import category_buttons


def render_controls(prefix, search_label, placeholder, categories, *, sort_options=()):
    out = '<div class="gal-filters" data-gal-controls hidden>'
    out += f'<label for="{prefix}-search">{escape(search_label)}</label>'
    out += f'<input id="{prefix}-search" type="search" data-gal-search placeholder="{escape(placeholder, quote=True)}" aria-describedby="{prefix}-help">'
    out += f'<p class="gal-filter-help" id="{prefix}-help">Select any matching option within a category. Different categories and search must all match.</p>'
    for key, label, values in categories:
        if key == "subgroups":
            out += category_buttons(key, label, values)
    for key, label, values in categories:
        if key != "subgroups":
            out += category_buttons(key, label, values)
    out += '<div class="gal-filter-actions">'
    if sort_options:
        out += f'<div class="gal-sort"><label for="{prefix}-sort">Sort analyses</label><select id="{prefix}-sort" data-gal-sort>'
        for value, label in sort_options:
            out += (
                f'<option value="{escape(value, quote=True)}">{escape(label)}</option>'
            )
        out += "</select></div>"
    out += '<div class="gal-filter-action-buttons"><button type="button" data-gal-expand-all aria-pressed="false">Expand all</button>'
    return (
        out
        + '<button type="button" class="gal-reset" data-gal-reset>Reset filters</button></div></div></div>\n'
    )
