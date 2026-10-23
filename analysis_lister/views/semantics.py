# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Pure, versioned interpretation of curated fields with input evidence."""

import re
from datetime import datetime

from .models import Decision

ONGOING = {"phase0", "editorial_review", "preapproved", "publication_review"}
STAGE_LABELS = {
    "phase0": "Phase 0",
    "editorial_review": "Editorial review",
    "preapproved": "Pre-approved",
    "publication_review": "Publication review",
    "closed": "Closed",
    "not_started": "Not started",
    "completed": "Completed",
    "unknown": "Needs review",
}


def iso_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def group_membership(record, group):
    groups = record.get("gal_groups") or {}
    inputs = {
        "gal_groups.leadingGroup": groups.get("leadingGroup"),
        "gal_groups.otherGroups": groups.get("otherGroups", []),
    }
    leading = groups.get("leadingGroup") == group
    additional = group in (groups.get("otherGroups") or [])
    return Decision(
        "group-membership/v1",
        leading or additional,
        "leading" if leading else "additional" if additional else "not affiliated",
        inputs,
    )


def publication_state(record, resource):
    status = record.get("status")
    phase = (
        record.get("publicationPhase") or {}
        if resource == "papers"
        else record.get("phase1") or {}
    )
    number = record.get("finalReferenceCode") or record.get("gal_finalReferenceCode")
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
        pattern = (
            r"ATLAS-CONF-\d{4}-\d+"
            if resource == "confnotes"
            else r"ATL-PHYS-PUB-\d{4}-\d+"
        )
        released = bool(
            re.fullmatch(pattern, number or "")
            and phase.get("publicWebPageUrlForFiguresAndTables")
            and (status == "Phase 1 Finished" or iso_date(phase.get("releaseDate")))
        )
        if released:
            state, reason = (
                "released",
                "final note number and public URL with release evidence",
            )
        elif record.get("supersededBy"):
            state, reason = "superseded", "source records a superseding publication"
        elif status == "Phase 1 Active":
            state, reason = (
                "under_review",
                "active note review without release evidence",
            )
    return Decision("publication-state/v1", state, reason, inputs)


def analysis_state(record, linked_states):
    phase = record.get("phase0") or {}
    status = record.get("status")
    inputs = {
        "status": status,
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
    return Decision("analysis-state/v1", state, reason, inputs)


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
        "last-phase0-milestone/v1",
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
        "analysis-approval-progress/v2",
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
        "analysis-email-convention/v1",
        value,
        "addresses derived from native analysis reference using the CERN list naming convention; not verified",
        {"referenceCode": reference},
    )


def associated_paper_statuses(record, papers):
    """Expose native paper status after phase 0, without replacing analysis status."""
    return Decision(
        "associated-paper-status/v1",
        [paper for paper in papers if paper.get("status")]
        if record.get("status") == "Phase 0 Finished"
        else [],
        "native statuses of explicitly linked, resolved papers when analysis phase 0 is finished; missing status remains absent",
        {"analysis.status": record.get("status"), "linked_papers": papers},
    )


def subgroup_button_choices(group, recorded):
    """Use all recorded names in the exact group namespace, including older labels."""
    return Decision(
        "group-subgroup-buttons/v2",
        tuple(
            (name, name)
            for name in sorted(set(recorded))
            if name.startswith(group + "-")
        ),
        "recorded subgroup namespace matches the exact group prefix; no ownership inferred from co-occurrence",
        {"group": group, "recorded_names": sorted(set(recorded))},
    )


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
        "last-paper-milestone/v2",
        (latest[2], latest[0]) if latest else None,
        "latest valid recorded paper date; later review step breaks date ties; no inference from status",
        inputs,
    )


def analysis_review_order(progress):
    """Order by the exact displayed ticks, with later milestones taking precedence."""
    return Decision(
        "analysis-review-order/v2",
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
