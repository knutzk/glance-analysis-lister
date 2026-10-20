# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Module that provides subgroup definitions."""

from collections import namedtuple

# Named tuple definition used for the subgroups, see below.
Subgroup = namedtuple("Subgroup", "code id title output_dir")

# Define the three main subgroups of the top group.
TX = Subgroup("TX", "TOPQ - Top Quarks + X", "Top Quarks + X", "topx")
XS = Subgroup("XS", "TOPQ - Cross-section", "Cross-section", "xs")
PM = Subgroup("PM", "TOPQ - Top Properties and Mass", "Properties & Mass", "pm")

# Create a list object that contains all top subgroups.
TopGroups = [TX, XS, PM]

# Look-up of the subgroup definitions by their GLANCE identifier.
GroupsById = {g.id: g for g in TopGroups}


def top_subgroups(subgroups: list[str]) -> list[Subgroup]:
    """Return the top WG subgroups of an entry, in the order of TopGroups.

    GLANCE lists the subgroups of an entry alphabetically and does not
    record which of them leads the analysis, so the order of the input is
    meaningless. Sorting by TopGroups instead makes the result depend only
    on our own definitions.

    Args:
        subgroups: Subgroup ids of an entry, as taken from GLANCE.

    Returns:
        The matching top WG subgroups; empty if the entry belongs to none.

    """
    return [g for g in TopGroups if g.id in subgroups]


def canonical_subgroup(subgroups: list[str]) -> Subgroup | None:
    """Return the subgroup whose page is the canonical one for an entry.

    Entries that belong to several subgroups are rendered on several
    subgroup pages. Global pages need to link to exactly one of them, and
    this function picks it.

    Args:
        subgroups: Subgroup ids of an entry, as taken from GLANCE.

    Returns:
        The first matching top WG subgroup, or None if there is none.

    """
    groups = top_subgroups(subgroups)
    return groups[0] if groups else None
