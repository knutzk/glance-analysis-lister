# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Analyses preparation and traceable interpretation of curated records."""

import re

from attrs import asdict

from .common import group_membership, iso_date
from .models import AnalysisRow, Decision
from .publications import last_paper_milestone

ONGOING = {
    "phase0",
    "editorial_review",
    "preapproved",
    "awaiting_publication_review",
    "publication_review",
}


STAGE_LABELS = {
    "phase0": "Phase 0",
    "editorial_review": "Editorial review",
    "preapproved": "Pre-approved",
    "awaiting_publication_review": "Awaiting publication review",
    "publication_review": "Publication review",
    "closed": "Closed",
    "not_started": "Not started",
    "completed": "Completed",
    "unknown": "Needs review",
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


def analysis_email_lists(reference):
    """Conventional CERN list addresses; availability is not verified offline."""
    value = []
    list_reference = reference.removeprefix("ANA-")
    if re.fullmatch(r"[A-Za-z]+-\d{4}-\d+", list_reference):
        value = [
            {
                "label": label,
                "address": f"atlas-{list_reference.lower()}-{suffix}@cern.ch",
            }
            for label, suffix in (
                ("Analysis team", "analysis-team"),
                ("Editorial board and conveners", "edboard-conveners"),
            )
        ]
    return Decision(
        "analysis-email-convention",
        value,
        "addresses derived from native analysis reference using the CERN list naming convention; not verified",
        {"referenceCode": reference},
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


def prepare_analyses(analyses, publications, linked, issues, profile):
    traces = []
    ongoing, review = [], []
    for reference, record in analyses.items():
        membership = group_membership(record, profile.group)
        links = list(linked[reference].values())
        state = analysis_state(record, links)
        milestone = last_milestone(record)
        email_lists = analysis_email_lists(reference)
        progress_inputs = []
        paper_status_inputs = []
        paper_milestones = []
        for link in links:
            target = publications.get((link["resource"], link["reference"]))
            publication = target[0] if target else {}
            if link["resource"] == "papers" and target:
                paper_milestones.append(
                    {
                        "reference": link["reference"],
                        "milestone": asdict(last_paper_milestone(publication)),
                        "relationship": link["relationship"],
                    }
                )
            if link["resource"] == "papers":
                paper_status_inputs.append(
                    {
                        "reference": link["reference"],
                        "status": publication.get("status"),
                        "state": link["state"],
                        "relationship": link["relationship"],
                    }
                )
            progress_inputs.append(
                {
                    **link,
                    "draftReleasedDate": (publication.get("phase1") or {}).get(
                        "draftReleasedDate"
                    ),
                    "draft2ReleasedDate": (publication.get("phase2") or {}).get(
                        "draft2ReleasedDate"
                    ),
                    "pgcApprovalDate": (publication.get("phase1") or {}).get(
                        "pgcApprovalDate"
                    ),
                }
            )
        progress = approval_progress(record, progress_inputs)
        paper_statuses = associated_paper_statuses(record, paper_status_inputs)
        review_order = analysis_review_order(progress)
        include = membership.value and state.value in ONGOING
        trace = {
            "resource": "analyses",
            "reference": reference,
            "membership": asdict(membership),
            "state": asdict(state),
            "review_order": asdict(review_order),
            "milestone": asdict(milestone),
            "approval_progress": asdict(progress),
            "associated_paper_statuses": asdict(paper_statuses),
            "paper_milestones": paper_milestones,
            "email_lists": asdict(email_lists),
            "editorial_board_chairs": {
                "phase0.gal_editorialBoardChairs": (record.get("phase0") or {}).get(
                    "gal_editorialBoardChairs"
                )
                or []
            },
            "relationship_issues": issues[reference],
            "inclusion": asdict(
                Decision(
                    "group-ongoing-collection",
                    include,
                    "affiliated analysis with an explicitly recognised ongoing state",
                    {"membership": membership.value, "state": state.value},
                )
            ),
        }
        traces.append(trace)
        if not membership.value:
            continue
        phase = record.get("phase0") or {}
        row = AnalysisRow(
            reference,
            record.get("shortTitle") or reference,
            state.value,
            tuple(record.get("gal_analysisContacts") or []),
            tuple(record.get("gal_contactEditors") or []),
            tuple(record.get("gal_internalNoteEditors") or []),
            tuple(phase.get("gal_editorialBoard") or []),
            record.get("gal_groups") or {},
            tuple((record.get("metadata") or {}).get("gal_keywords") or []),
            milestone.value,
            tuple(
                (record.get("documentation") or {}).get("supportingInternalDocuments")
                or []
            ),
            tuple(links),
            {
                "subgroups": list(
                    dict.fromkeys(
                        name
                        for name in [
                            (record.get("gal_groups") or {}).get("leadingSubgroup"),
                            *((record.get("gal_groups") or {}).get("subgroups") or []),
                        ]
                        if name
                    )
                ),
                "leading_subgroup": (record.get("gal_groups") or {}).get(
                    "leadingSubgroup"
                ),
                "keywords": list(
                    (record.get("metadata") or {}).get("gal_keywords") or []
                ),
                "triggers": list(
                    (record.get("metadata") or {}).get("gal_triggers") or []
                ),
                "statistical_tools": list(
                    (record.get("metadata") or {}).get("gal_statisticalTools") or []
                ),
                "stage": state.value,
                "stage_order": review_order.value,
                "participation": "leading"
                if membership.reason == "leading"
                else "additional",
                "text": " ".join(
                    [
                        reference,
                        record.get("shortTitle") or "",
                        *record.get("gal_analysisContacts", []),
                        *record.get("gal_contactEditors", []),
                        *record.get("gal_internalNoteEditors", []),
                        *(phase.get("gal_editorialBoard") or []),
                        *((record.get("metadata") or {}).get("gal_keywords") or []),
                        *((record.get("metadata") or {}).get("gal_triggers") or []),
                        *(
                            (record.get("metadata") or {}).get("gal_statisticalTools")
                            or []
                        ),
                    ]
                ),
            },
            tuple(progress.value),
            record.get("status") or "Not recorded",
            tuple(email_lists.value),
            tuple(phase.get("gal_editorialBoardChairs") or []),
            tuple(paper_statuses.value),
            tuple(paper_milestones),
        )
        if include:
            ongoing.append(row)
        elif state.value == "unknown":
            review.append(row)
    return ongoing, review, traces
