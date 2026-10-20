# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Review manual analysis relationships against the current retrieval scope."""

import logging

from .lookup_dicts.clones import Clones


def lookup_review_notices(registry, *, relevant_refs=None):
    """Check full-snapshot membership for relationships relevant to a view.

    Records excluded by presentation filters are not missing from the snapshot.
    Entirely absent historical mappings are irrelevant to the current data.
    """
    entries = registry.entries
    notices = []
    for ref, origin in sorted(Clones.items()):
        missing = [code for code in (ref, origin) if code not in entries]
        present = {ref, origin}.intersection(entries)
        if relevant_refs is not None and not present.intersection(relevant_refs):
            continue
        if len(missing) == 1:
            notices.append(
                (
                    logging.INFO,
                    f"{ref}: clone/duplicate relationship has references absent from "
                    f"this snapshot: {', '.join(missing)}. Retain historical mappings.",
                )
            )
    return notices
