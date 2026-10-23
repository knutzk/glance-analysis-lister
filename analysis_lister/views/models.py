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
class PublicationRow:
    resource: str
    reference: str
    label: str
    title: str
    state: str
    date: str | None
    subgroups: tuple
    citations: tuple
    filter_metadata: dict
    provenance: dict
    details: dict


@frozen
class GroupView:
    profile: object
    ongoing: tuple
    needs_review: tuple
    publications: tuple
    recent: tuple
    decisions: tuple
    source_metadata: dict
    publication_filters: dict
    subgroup_buttons: tuple
    subgroup_button_provenance: dict

    @property
    def archive(self):
        """Submitted/published papers and released notes, newest known dates first."""
        return tuple(
            sorted(
                (
                    row
                    for row in self.publications
                    if row.state in {"submitted", "published", "released"}
                ),
                key=lambda row: (
                    row.date is not None,
                    row.date or "",
                    row.resource,
                    row.reference,
                ),
                reverse=True,
            )
        )
