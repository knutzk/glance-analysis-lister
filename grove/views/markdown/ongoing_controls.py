# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Native, progressive filter controls shared by cards and tables."""

from html import escape

from .controls import category_buttons


def render_controls(prefix, search_label, placeholder, categories, *, sort_options=()):
    out = '<div class="grove-filters" data-grove-controls hidden>'
    out += f'<label for="{prefix}-search">{escape(search_label)}</label>'
    out += f'<input id="{prefix}-search" type="search" data-grove-search placeholder="{escape(placeholder, quote=True)}" aria-describedby="{prefix}-help">'
    out += f'<p class="grove-filter-help" id="{prefix}-help">Select any matching option within a category. Different categories and search must all match.</p>'
    for key, label, values in categories:
        if key == "subgroups":
            out += category_buttons(key, label, values)
    for key, label, values in categories:
        if key != "subgroups":
            out += category_buttons(key, label, values)
    out += '<div class="grove-filter-actions">'
    if sort_options:
        out += f'<div class="grove-sort"><label for="{prefix}-sort">Sort analyses</label><select id="{prefix}-sort" data-grove-sort>'
        for value, label in sort_options:
            out += (
                f'<option value="{escape(value, quote=True)}">{escape(label)}</option>'
            )
        out += "</select></div>"
    out += '<div class="grove-filter-action-buttons"><button type="button" data-grove-expand-all aria-pressed="false">Expand all</button>'
    return (
        out
        + '<button type="button" class="grove-reset" data-grove-reset>Reset filters</button></div></div></div>\n'
    )
