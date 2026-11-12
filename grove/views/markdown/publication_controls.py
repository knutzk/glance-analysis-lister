# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publication search controls, independent of ongoing-analysis search."""

from .controls import category_buttons, date_controls, expansion_control, search_control


def render_controls(prefix, search_label, placeholder, categories):
    out = '<div class="gal-filters" data-gal-controls hidden>'
    out += search_control(prefix, search_label, placeholder)
    out += f'<p class="gal-filter-help" id="{prefix}-help">Selected publication statuses are combined with OR; dates and search must also match.</p>'
    out += date_controls(prefix)
    out += '<div class="gal-publication-filter-row">'
    for key, label, values in categories:
        out += category_buttons(key, label, values)
    out += '<div class="gal-filter-actions">' + expansion_control()
    return (
        out
        + '<button type="button" class="gal-reset" data-gal-reset>Reset filters</button></div></div></div>\n'
    )
