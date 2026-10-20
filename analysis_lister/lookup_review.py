# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Review manual analysis relationships against the current retrieval scope."""

import logging

from .lookup_dicts.clones import Clones


def lookup_review_notices(registry):
    """Report missing references as informational; partial scopes are expected."""
    entries = registry.entries
    notices = []
    for ref, origin in sorted(Clones.items()):
        missing = [code for code in (ref, origin) if code not in entries]
        if missing:
            notices.append(
                (
                    logging.INFO,
                    f"{ref}: clone/duplicate relationship has references absent from "
                    f"this snapshot: {', '.join(missing)}. Retain historical mappings.",
                )
            )
    return notices
