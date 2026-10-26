# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Analyses preparation and traceable interpretation of curated records."""

import re

from attrs import asdict

from .analysis_states import (
    ONGOING,
    analysis_review_order,
    analysis_state,
    approval_progress,
    associated_paper_statuses,
    last_milestone,
)
from .common import group_membership
from .models import AnalysisRow, Decision
from .publication_states import last_paper_milestone


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
