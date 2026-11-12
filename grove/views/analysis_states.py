# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Traceable analysis states, milestones, approval progress and ordering."""

from .common import iso_date
from .models import Decision

ONGOING = {
    "phase0",
    "editorial_review",
    "preapproved",
    "awaiting_publication_review",
    "publication_review",
}


def analysis_state(record, linked_states):
    phase = record.get("phase0") or {}
    status = record.get("status")
    inputs = {
        "status": status,
        "phase0.state": phase.get("state"),
        "phase0.pgcOrSgcSignOffDate": phase.get("pgcOrSgcSignOffDate"),
        "phase0.editorialBoardFormedDate": phase.get("editorialBoardFormedDate"),
        "phase0.gal_editorialBoard": phase.get("gal_editorialBoard", []),
        "linked_publication_states": linked_states,
    }
    state, reason = "unknown", "source does not establish an ongoing or completed state"
    if status == "Closed":
        state, reason = "closed", "source status is Closed"
    elif status == "Created":
        state, reason = "not_started", "source status is Created"
    elif status in {"Phase 0 Active", "Phase 0 Finished"}:
        states = [entry["state"] for entry in linked_states]
        if "under_review" in states:
            state, reason = (
                "publication_review",
                "at least one explicitly linked publication is under review",
            )
        elif states and all(
            value in {"published", "submitted", "released", "closed", "superseded"}
            for value in states
        ):
            state, reason = (
                "completed",
                "all resolved publications are beyond active review",
            )
        elif (
            status == "Phase 0 Finished"
            and "not_started" in states
            and all(
                value
                in {
                    "not_started",
                    "published",
                    "submitted",
                    "released",
                    "closed",
                    "superseded",
                }
                for value in states
            )
        ):
            state, reason = (
                "awaiting_publication_review",
                "phase 0 finished and at least one linked publication is Created; all other linked publications are resolved and beyond active review",
            )
        elif status == "Phase 0 Active":
            if iso_date(phase.get("pgcOrSgcSignOffDate")):
                state, reason = "preapproved", "phase-0 sign-off date is recorded"
            elif phase.get("gal_editorialBoard") or iso_date(
                phase.get("editorialBoardFormedDate")
            ):
                state, reason = (
                    "editorial_review",
                    "editorial board or its formation date is recorded",
                )
            else:
                state, reason = (
                    "phase0",
                    "active phase 0 without board or sign-off evidence",
                )
    return Decision("analysis-state", state, reason, inputs)


def last_milestone(record):
    phase = record.get("phase0") or {}
    fields = [
        ("startDate", "Phase 0 started"),
        ("gal_eoiMeetingDates", "Expression of interest"),
        ("gal_editorialBoardRequestMeetingDates", "Editorial board requested"),
        ("editorialBoardFormedDate", "Editorial board formed"),
        ("gal_preApprovalMeetingDates", "Pre-approval meeting"),
        ("pgcOrSgcSignOffDate", "Pre-approval sign-off"),
        ("gal_approvalMeetingDates", "Approval meeting"),
    ]
    inputs, candidates = {}, []
    for priority, (field, label) in enumerate(fields):
        raw = phase.get(field)
        inputs["phase0." + field] = raw
        for value in raw if isinstance(raw, list) else [raw]:
            day = iso_date(value)
            if day:
                candidates.append((day, priority, label))
    latest = max(candidates) if candidates else None
    value = (latest[2], latest[0]) if latest else None
    return Decision(
        "last-phase0-milestone",
        value,
        "latest recorded date; later review step breaks date ties"
        if latest
        else "no valid phase-0 milestone date",
        inputs,
    )


def approval_progress(record, publications):
    """Keep each milestone independent: a later step does not invent missing dates."""
    phase = record.get("phase0") or {}
    board_date = iso_date(phase.get("editorialBoardFormedDate"))
    pre_date = iso_date(phase.get("pgcOrSgcSignOffDate"))
    approvals = [
        iso_date(publication.get("pgcApprovalDate")) for publication in publications
    ]
    approval_date = min((day for day in approvals if day), default=None)
    circulations = [
        min(
            (
                day
                for p in publications
                if p.get("resource") == "papers" and (day := iso_date(p.get(field)))
            ),
            default=None,
        )
        for field in ("draftReleasedDate", "draft2ReleasedDate")
    ]
    return Decision(
        "analysis-approval-progress",
        [
            {
                "label": "EdBoard assignment",
                "reached": bool(board_date or phase.get("gal_editorialBoard")),
                "date": board_date,
            },
            {
                "label": "Pre-approval sign-off",
                "reached": bool(pre_date),
                "date": pre_date,
            },
            {
                "label": "Approval sign-off",
                "reached": bool(approval_date),
                "date": approval_date,
            },
            *[
                {
                    "label": f"ATLAS circulation {number}",
                    "reached": bool(day),
                    "date": day,
                }
                for number, day in enumerate(circulations, 1)
            ],
        ],
        "independent recorded milestones; board membership also establishes assignment; linked publication PGC approval establishes approval sign-off; linked paper phase1.draftReleasedDate and phase2.draft2ReleasedDate establish the respective ATLAS circulations; no inference from status or other milestones",
        {
            "phase0.editorialBoardFormedDate": phase.get("editorialBoardFormedDate"),
            "phase0.gal_editorialBoard": phase.get("gal_editorialBoard"),
            "phase0.pgcOrSgcSignOffDate": phase.get("pgcOrSgcSignOffDate"),
            "linked_publications": publications,
        },
    )


def associated_paper_statuses(record, papers):
    """Expose native paper status after phase 0, without replacing analysis status."""
    return Decision(
        "associated-paper-status",
        [paper for paper in papers if paper.get("status")]
        if record.get("status") == "Phase 0 Finished"
        else [],
        "native statuses of explicitly linked, resolved papers when analysis phase 0 is finished; missing status remains absent",
        {"analysis.status": record.get("status"), "linked_papers": papers},
    )


def analysis_review_order(progress):
    """Order by the exact displayed ticks, with later milestones taking precedence."""
    return Decision(
        "analysis-review-order",
        sum(1 << index for index, step in enumerate(progress.value) if step["reached"]),
        "visible approval ticks determine ordering; each later tick outweighs all earlier ticks combined; identical tick patterns use identifier order; no separate status or date ordering",
        {
            "approval_progress": {
                "rule": progress.rule,
                "value": progress.value,
                "inputs": progress.inputs,
            }
        },
    )
