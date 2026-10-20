# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Manual clone lineage and conservative publication precedence."""

from ..lookup_dicts.clones import Clones


def clone_exclusions(entries):
    """Derive exclusions without deleting records or overwriting GLANCE states.

    A live paper supersedes ancestor CONF notes, including during paper review.
    Known finished clone-family records without publications are excluded.
    Active siblings and every distinct paper remain eligible. Missing
    descendants never supersede CONF notes.
    """
    from .analysis import Analysis
    from .confnote import ConfNote
    from .enums import PublicationState as State
    from .paper import Paper

    children = {ref: set() for ref in entries}
    related = set(Clones) | set(Clones.values())
    for child, parent in Clones.items():
        if parent == child:
            raise ValueError(f"Self-referencing clone relationship: {child}")
        if parent in entries and child in entries:
            children[parent].add(child)

    def reachable(ref, edges):
        seen = {ref}
        pending = list(edges[ref])
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(edges[node])
        return seen - {ref}

    # A directed cycle is invalid provenance, not a reason to drop publications.
    for ref in entries:
        if any(
            ref in reachable(child, children) or child == ref for child in children[ref]
        ):
            raise ValueError("Cycle in clone relationships")
    excluded = set()
    for ref, entry in entries.items():
        if isinstance(entry, ConfNote):
            if any(
                isinstance(entries[other], Paper)
                and entries[other].pub_state
                in {State.PHASE1_OR_2, State.SUBMITTED_TO_JOURNAL, State.PUBLISHED}
                for other in reachable(ref, children)
            ):
                excluded.add(ref)
        elif (
            type(entry) is Analysis
            and entry.pub_state == State.PAST_PHASE0
            and ref in related
        ):
            excluded.add(ref)
    return excluded
