# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publication search controls, independent of ongoing-analysis search."""

from html import escape

from .filtering import category_buttons


def date_controls(prefix, *, release=False):
    noun = "Released" if release else "Published"
    prefix = escape(prefix, quote=True)
    return (
        '<div class="gal-date-filters">'
        + "".join(
            f'<label for="{prefix}-{bound}">{noun} {bound}<input id="{prefix}-{bound}" type="month" data-gal-date-{bound}></label>'
            for bound in ("after", "before")
        )
        + '<span class="gal-date-help">Selected months included; undated entries excluded only when a before date is set.</span></div>'
    )


def expansion_control():
    return '<button type="button" data-gal-archive-expand-all aria-pressed="false">Expand all</button>'


def search_control(prefix, label, placeholder):
    prefix = escape(prefix, quote=True)
    return f'<label for="{prefix}-search">{escape(label)}</label><input id="{prefix}-search" type="search" data-gal-search placeholder="{escape(placeholder, quote=True)}">'


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
