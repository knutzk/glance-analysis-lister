# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Small view datasets and machine-readable derivation evidence."""

from attrs import frozen


@frozen
class Decision:
    rule: str
    value: object
    reason: str
    inputs: dict


@frozen
class AnalysisRow:
    reference: str
    title: str
    stage: str
    contacts: tuple
    editors: tuple
    internal_editors: tuple
    board: tuple
    groups: dict
    keywords: tuple
    milestone: tuple | None
    documents: tuple
    publications: tuple
    filter_metadata: dict
    progress: tuple
    status: str
    email_lists: tuple
    board_chairs: tuple
    paper_statuses: tuple
    paper_milestones: tuple


@frozen
class GroupView:
    profile: object
    ongoing: tuple
    needs_review: tuple
    decisions: tuple
    source_metadata: dict
    subgroup_buttons: tuple
    subgroup_button_provenance: dict
