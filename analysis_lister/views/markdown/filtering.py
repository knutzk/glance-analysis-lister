# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Native, progressive filter controls shared by cards and tables."""

from html import escape


def category_buttons(key, label, values):
    if not values:
        return ""
    out = f'<fieldset data-gal-filter="{escape(key, quote=True)}"><legend>{escape(label)}</legend><div class="gal-filter-buttons">'
    for value, title in values:
        out += f'<button type="button" data-gal-value="{escape(value, quote=True)}" aria-pressed="false">{escape(title)}</button>'
    return out + "</div></fieldset>"


def render_controls(
    prefix, search_label, placeholder, categories, *, dropdowns=(), sort_options=()
):
    out = '<div class="gal-filters" data-gal-controls hidden>'
    out += f'<label for="{prefix}-search">{escape(search_label)}</label>'
    out += f'<input id="{prefix}-search" type="search" data-gal-search placeholder="{escape(placeholder, quote=True)}" aria-describedby="{prefix}-help">'
    out += f'<p class="gal-filter-help" id="{prefix}-help">Select any matching option within a category. Different categories and search must all match.</p>'
    for key, label, values in categories:
        if key == "subgroups":
            out += category_buttons(key, label, values)
    if dropdowns:
        out += '<div class="gal-filter-dropdowns">'
        for key, label, values in dropdowns:
            field_id = f"{prefix}-{key}"
            out += f'<div class="gal-dropdown" data-gal-filter="{escape(key, quote=True)}">'
            if key in {"keywords", "triggers", "statistical_tools"}:
                out += f'<span class="gal-dropdown-label" id="{field_id}-label">{escape(label)}</span>'
            else:
                out += f'<label for="{field_id}">{escape(label)}</label>'
            if key in {"keywords", "triggers", "statistical_tools"}:
                default = "All " + label.lower()
                out += f'<details class="gal-multiselect"><summary aria-labelledby="{field_id}-label {field_id}-selection"><span id="{field_id}-selection" data-gal-selection-summary data-gal-default="{escape(default, quote=True)}">{escape(default)}</span></summary>'
                out += f'<div class="gal-multiselect-options" role="group" aria-labelledby="{field_id}-label">'
                if not values:
                    out += "<p>No recorded values</p>"
                for number, value in enumerate(values):
                    option_id = f"{field_id}-{number}"
                    out += f'<label for="{option_id}"><input id="{option_id}" type="checkbox" data-gal-choice value="{escape(value, quote=True)}">{escape(value)}</label>'
                out += "</div></details></div>"
            else:
                out += f'<select id="{field_id}" data-gal-select><option value="">All</option>'
                for value in values:
                    out += f'<option value="{escape(value, quote=True)}">{escape(value)}</option>'
                out += "</select></div>"
        out += "</div>"
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


def dropdown_options(rows):
    """Offer recorded metadata values; subgroup membership uses tag buttons."""
    return [
        (
            key,
            label,
            sorted({value for row in rows for value in row.filter_metadata[key]}),
        )
        for key, label in (
            ("keywords", "Keywords"),
            ("triggers", "Triggers"),
            ("statistical_tools", "Statistical tools"),
        )
    ]


def active_subgroup_buttons(rows, choices):
    """Offer only choices with matches in this page's unfiltered collection."""
    available = {name for row in rows for name in row.filter_metadata["subgroups"]}
    return [(value, label) for value, label in choices if value in available]
