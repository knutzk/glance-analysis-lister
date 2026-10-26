# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared plain-text people presentation for all view formats."""


def board_names(members, chairs):
    """Mark recorded chairs, retaining chair-only entries and source order.

    Return plain text; each renderer remains responsible for escaping it.
    """
    return [
        name + (" (chair)" if name in chairs else "")
        for name in dict.fromkeys([*members, *chairs])
    ]
