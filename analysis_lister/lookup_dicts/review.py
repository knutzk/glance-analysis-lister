# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Snapshot-relative review notices for factual overrides; never delete entries."""

import logging

from ..glance.paper import Paper
from .doi_order import DoiOrder
from .known_duplicates import KnownDuplicates


def lookup_review_notices(registry):
    """Return (logging level, message) pairs for overrides needing review.

    Absence from this snapshot is not proof of removal from GLANCE. Historical
    titles and journal citations are intentionally not reported as stale.
    """
    entries = registry.entries
    unaccounted = {entry.ref_code for entry in registry.unaccounted}
    listed = {
        entry.ref_code
        for entry in [
            *registry.analyses,
            *registry.papers,
            *registry.confnotes,
            *registry.pubnotes,
        ]
    }
    notices = []
    for ref, target in sorted(KnownDuplicates.items()):
        reasons = []
        if ref not in entries:
            reasons.append("duplicate is absent from this snapshot")
        elif ref not in unaccounted:
            reasons.append(f"duplicate is now {entries[ref].pub_state.value}")
        if target not in entries:
            reasons.append(f"target {target} is absent from this snapshot")
        elif target not in listed:
            reasons.append(
                f"target {target} is {entries[target].pub_state.value} and appears on no page"
            )
        if reasons:
            notices.append(
                (
                    logging.WARNING,
                    f"{ref}: review analysis_lister/lookup_dicts/known_duplicates.py: "
                    + "; ".join(reasons)
                    + ". Check the mapping against GLANCE before changing it.",
                )
            )
    for ref in sorted(DoiOrder):
        if ref not in entries:
            notices.append(
                (
                    logging.INFO,
                    f"{ref}: analysis_lister/lookup_dicts/doi_order.py override is unused "
                    "in this snapshot; it may be historical. Retain unless confirmed obsolete.",
                )
            )
        elif not isinstance(entries[ref], Paper):
            notices.append(
                (
                    logging.WARNING,
                    f"{ref}: review analysis_lister/lookup_dicts/doi_order.py: "
                    f"record is {type(entries[ref]).__name__}, so its DOI override is unused.",
                )
            )
    return notices
