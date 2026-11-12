# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared accessible control markup, without collection-specific search logic."""

from html import escape


def category_buttons(key, label, values):
    if not values:
        return ""
    out = f'<fieldset data-grove-filter="{escape(key, quote=True)}"><legend>{escape(label)}</legend><div class="grove-filter-buttons">'
    for value, title in values:
        out += f'<button type="button" data-grove-value="{escape(value, quote=True)}" aria-pressed="false">{escape(title)}</button>'
    return out + "</div></fieldset>"


def date_controls(prefix, *, release=False):
    noun = "Released" if release else "Published"
    prefix = escape(prefix, quote=True)
    return (
        '<div class="grove-date-filters">'
        + "".join(
            f'<label for="{prefix}-{bound}">{noun} {bound}<input id="{prefix}-{bound}" type="month" data-grove-date-{bound}></label>'
            for bound in ("after", "before")
        )
        + '<span class="grove-date-help">Selected months included; undated entries excluded only when a before date is set.</span></div>'
    )


def expansion_control():
    return '<button type="button" data-grove-archive-expand-all aria-pressed="false">Expand all</button>'


def search_control(prefix, label, placeholder):
    prefix = escape(prefix, quote=True)
    return f'<label for="{prefix}-search">{escape(label)}</label><input id="{prefix}-search" type="search" data-grove-search placeholder="{escape(placeholder, quote=True)}">'
