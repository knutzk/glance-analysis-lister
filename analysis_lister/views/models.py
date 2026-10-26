# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Small view datasets and machine-readable derivation evidence."""

from typing import TypedDict

from attrs import frozen

from .profiles import GroupProfile


@frozen
class Decision:
    rule: str
    value: object
    reason: str
    inputs: dict


class RuleEvidence(TypedDict):
    rule: str
    value: object
    reason: str
    inputs: dict


class RecordMetadata(TypedDict, total=False):
    """Search text and record attributes, independent of available UI controls."""

    text: str
    subgroups: list[str]
    leading_subgroup: str | None
    keywords: list[str]
    triggers: list[str]
    statistical_tools: list[str]
    people: list[str]
    publication_type: str
    publication_status: str
    state: str
    stage: str
    stage_order: int
    participation: str


@frozen
class PublicationLink:
    label: str
    url: str | None


@frozen
class PeopleRole:
    label: str
    names: tuple[str, ...]


@frozen
class TagGroup:
    label: str
    values: tuple[str, ...]


@frozen
class NoteDetails:
    people: tuple[PeopleRole, ...]
    tags: tuple[TagGroup, ...]
    superseded: bool
    superseded_by: tuple[dict, ...]
    related_analysis: dict | None

    @classmethod
    def from_evidence(cls, value):
        if value is None:
            return None
        return cls(
            tuple(
                PeopleRole(person["label"], tuple(person["names"]))
                for person in value["people"]
            ),
            tuple(
                TagGroup(tag["label"], tuple(tag["values"])) for tag in value["tags"]
            ),
            value["superseded"],
            tuple(value["superseded_by"]),
            value["related_analysis"],
        )


@frozen
class PublicationDetails:
    last_milestone: tuple[str, str] | None
    publication_records: tuple[PublicationLink, ...]
    contacts: tuple[str, ...]
    editors: tuple[str, ...]
    board: tuple[str, ...]
    board_chairs: tuple[str, ...]
    groups: dict
    links: tuple[PublicationLink, ...]
    cds_url: str | None
    conf_note: NoteDetails | None
    pub_note: NoteDetails | None

    @classmethod
    def from_evidence(cls, value):
        return cls(
            value["last_milestone"],
            tuple(
                PublicationLink(link["label"], link["url"])
                for link in value["publication_records"]
            ),
            tuple(value["contacts"]),
            tuple(value["editors"]),
            tuple(value["board"]),
            tuple(value["board_chairs"]),
            value["groups"],
            tuple(
                PublicationLink(link["label"], link["url"]) for link in value["links"]
            ),
            value["cds_url"],
            NoteDetails.from_evidence(value["conf_note"]),
            NoteDetails.from_evidence(value["pub_note"]),
        )


@frozen
class AnalysisRow:
    reference: str
    title: str
    stage: str
    contacts: tuple
    editors: tuple
    board: tuple
    groups: dict
    keywords: tuple
    milestone: tuple | None
    documents: tuple
    publications: tuple
    metadata: RecordMetadata
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
    metadata: RecordMetadata
    provenance: dict[str, RuleEvidence | dict]
    details: PublicationDetails


@frozen
class GroupView:
    profile: GroupProfile
    ongoing: tuple[AnalysisRow, ...]
    needs_review: tuple[AnalysisRow, ...]
    publications: tuple[PublicationRow, ...]
    decisions: tuple
    source_metadata: dict
    controls: dict
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
