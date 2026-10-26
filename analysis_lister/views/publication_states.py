# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Traceable publication lifecycle and dated paper milestones."""

import re

from ..registry.public_identifiers import PUB_PATTERN, final_identifier
from .common import iso_date
from .models import Decision


def publication_state(record, resource):
    status = record.get("status")
    phase = (
        record.get("publicationPhase") or {}
        if resource == "papers"
        else record.get("phase1") or {}
    )
    number = final_identifier(record, resource) if resource != "papers" else None
    inputs = {"status": status}
    if resource == "papers":
        inputs.update(
            {
                "publicationPhase.publishedOnlineDate": phase.get(
                    "publishedOnlineDate"
                ),
                "publicationPhase.arXivSubmissionDate": phase.get(
                    "arXivSubmissionDate"
                ),
            }
        )
    else:
        inputs.update(
            {
                "finalReferenceCode": record.get("finalReferenceCode"),
                "gal_finalReferenceCode": record.get("gal_finalReferenceCode"),
                "phase1.releaseDate": phase.get("releaseDate"),
                "phase1.publicWebPageUrlForFiguresAndTables": phase.get(
                    "publicWebPageUrlForFiguresAndTables"
                ),
                "supersededBy": record.get("supersededBy", []),
            }
        )
    state, reason = "unknown", "unrecognised or incomplete publication state"
    if status == "Closed":
        state, reason = "closed", "source status is Closed"
    elif status == "Created":
        state, reason = "not_started", "source status is Created"
    elif resource == "papers":
        if status not in {
            "Phase 1 Active",
            "Phase 2 Active",
            "Publication Phase Active",
            "Publication Phase Finished",
        }:
            pass
        elif (
            iso_date(phase.get("publishedOnlineDate"))
            or status == "Publication Phase Finished"
        ):
            state, reason = (
                "published",
                "publication date or completed publication phase",
            )
        elif iso_date(phase.get("arXivSubmissionDate")):
            state, reason = "submitted", "arXiv submission date is recorded"
        else:
            state, reason = (
                "under_review",
                "active publication phase without submission date",
            )
    else:
        pattern = r"ATLAS-CONF-\d{4}-\d+" if resource == "confnotes" else PUB_PATTERN
        released = bool(
            re.fullmatch(pattern, number or "")
            and (status == "Phase 1 Finished" or iso_date(phase.get("releaseDate")))
        )
        if released:
            state, reason = (
                "released",
                "final note number with release evidence",
            )
        elif record.get("supersededBy"):
            state, reason = "superseded", "source records a superseding publication"
        elif status == "Phase 1 Active":
            state, reason = (
                "under_review",
                "active note review without release evidence",
            )
    return Decision("publication-state", state, reason, inputs)


PAPER_MILESTONES = {
    "phase1": (
        ("startDate", "Phase 1 started"),
        ("editorialBoardFormedDate", "Editorial board formed"),
        ("pgcApprovalDate", "Approval sign-off"),
        ("editorialBoardDraftSignOffDate", "Editorial board draft sign-off"),
        ("languageEditorsSignOffDate", "Language editors sign-off"),
        ("draftReleasedDate", "ATLAS circulation 1"),
        ("presentationDate", "Paper presentation"),
        ("atlasMeetingDate", "ATLAS meeting"),
        ("pubcommSignOffDate", "PubCom sign-off"),
    ),
    "phase2": (
        ("startDate", "Phase 2 started"),
        ("editorialBoardDraft2SignOffDate", "Editorial board draft-2 sign-off"),
        ("draft2SentToCernDate", "Draft 2 sent to CERN"),
        ("draft2CernSignOffDate", "CERN draft-2 sign-off"),
        ("draft2ReleasedDate", "ATLAS circulation 2"),
        ("editorialBoardRevisedSignOffDate", "Editorial board revised-draft sign-off"),
        ("pubcommChairOrDeputySignOffDate", "PubCom chair sign-off"),
        ("spokespersonDelegatedSignOffDate", "Spokesperson delegate sign-off"),
        ("spokespersonOrDeputySignOffDate", "Spokesperson sign-off"),
        ("paperClosureDate", "Paper closure"),
    ),
    "publicationPhase": (
        ("startDate", "Publication phase started"),
        ("arXivSubmissionDate", "arXiv submission"),
        ("firstRefereeReportDate", "First referee report"),
        ("journalAcceptanceDate", "Journal acceptance"),
        ("firstProofDate", "First proof"),
        ("publishedOnlineDate", "Published online"),
    ),
}


def last_paper_milestone(record):
    """Choose the latest valid dated paper event, with stable review-order ties."""
    inputs, candidates = {}, []
    for section, fields in PAPER_MILESTONES.items():
        for field, label in fields:
            raw = (record.get(section) or {}).get(field)
            inputs[section + "." + field] = raw
            day = iso_date(raw)
            if day:
                phase = {
                    "phase1": "Phase 1",
                    "phase2": "Phase 2",
                    "publicationPhase": "Submission",
                }[section]
                event = "Started" if field == "startDate" else label
                candidates.append((day, len(inputs), f"{phase} · {event}"))
    latest = max(candidates) if candidates else None
    return Decision(
        "last-paper-milestone",
        (latest[2], latest[0]) if latest else None,
        "latest valid recorded paper date; later review step breaks date ties; no inference from status",
        inputs,
    )
