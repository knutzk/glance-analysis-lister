# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Common preparation and traceable interpretation of curated records."""

from datetime import datetime

from .models import Decision


def iso_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def group_membership(record, group):
    groups = record.get("gal_groups") or {}
    inputs = {
        "gal_groups.leadingGroup": groups.get("leadingGroup"),
        "gal_groups.otherGroups": groups.get("otherGroups", []),
    }
    leading = groups.get("leadingGroup") == group
    additional = group in (groups.get("otherGroups") or [])
    return Decision(
        "group-membership",
        leading or additional,
        "leading" if leading else "additional" if additional else "not affiliated",
        inputs,
    )


def subgroup_button_choices(group, recorded):
    """Use all recorded names in the exact group namespace, including older labels."""
    return Decision(
        "group-subgroup-buttons",
        tuple(
            (name, name)
            for name in sorted(set(recorded))
            if name.startswith(group + "-")
        ),
        "recorded subgroup namespace matches the exact group prefix; no ownership inferred from co-occurrence",
        {"group": group, "recorded_names": sorted(set(recorded))},
    )
