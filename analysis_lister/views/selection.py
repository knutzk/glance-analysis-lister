# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Select group collections once, retaining the reasons behind every decision."""

from attrs import asdict

from ..registry.reader import LINK_RESOURCES
from ..registry.schema import record_key
from .models import AnalysisRow, Decision, GroupView
from .semantics import (
    ONGOING,
    analysis_email_lists,
    analysis_review_order,
    analysis_state,
    approval_progress,
    associated_paper_statuses,
    group_membership,
    last_milestone,
    last_paper_milestone,
    publication_state,
    subgroup_button_choices,
)


def prepare_group(registry, profile):
    analyses = {row["referenceCode"]: row for row in registry.records("analyses")}
    publications, traces = {}, []
    linked = {reference: {} for reference in analyses}
    issues = {reference: [] for reference in analyses}
    for resource in ("papers", "confnotes", "pubnotes"):
        for record in registry.records(resource):
            reference = record_key(record, resource)
            state = publication_state(record, resource)
            membership = group_membership(record, profile.group)
            relation = record.get("relatedAnalysis")
            related = None
            if isinstance(relation, dict) and relation.get("type") == "Analysis":
                related = analyses.get(relation.get("referenceCode"))
                if related is not None:
                    linked[related["referenceCode"]][resource, reference] = {
                        "resource": resource,
                        "reference": reference,
                        "state": state.value,
                        "relationship": "publication.relatedAnalysis",
                    }
            groups = record.get("gal_groups") or {}
            if (
                not groups.get("leadingGroup")
                and not groups.get("otherGroups")
                and related is not None
            ):
                inherited = group_membership(related, profile.group)
                membership = Decision(
                    "publication-group-fallback/v1",
                    inherited.value,
                    "unassigned publication uses its explicitly linked analysis affiliation",
                    {
                        "publication.gal_groups": groups,
                        "relatedAnalysis": relation,
                        "analysis_group_evidence": asdict(inherited),
                    },
                )
            publications[resource, reference] = (record, state)
            traces.append(
                {
                    "resource": resource,
                    "reference": reference,
                    "membership": asdict(membership),
                    "state": asdict(state),
                    "relatedAnalysis": relation,
                    "relationship_issue": "unresolved relatedAnalysis"
                    if relation and related is None
                    else None,
                }
            )
    # Reconcile outbound links against publication-owned relationships.
    for reference, record in analyses.items():
        for relation in record.get("relatedPublications") or []:
            resource = LINK_RESOURCES.get(relation.get("type"))
            key = resource, relation.get("referenceCode")
            target = publications.get(key)
            if target is None:
                issues[reference].append(
                    {"link": relation, "reason": "unresolved publication link"}
                )
                linked[reference][key] = {
                    "resource": resource,
                    "reference": key[1],
                    "state": "unknown",
                    "relationship": "unresolved analysis.relatedPublications",
                }
                continue
            back = target[0].get("relatedAnalysis")
            if back and (
                back.get("type") != "Analysis" or back.get("referenceCode") != reference
            ):
                issues[reference].append(
                    {
                        "link": relation,
                        "reason": "publication points to a different analysis",
                        "relatedAnalysis": back,
                    }
                )
                continue
            if key not in linked[reference]:
                linked[reference][key] = {
                    "resource": resource,
                    "reference": key[1],
                    "state": target[1].value,
                    "relationship": "analysis.relatedPublications (one-way)",
                }
                issues[reference].append(
                    {"link": relation, "reason": "one-way publication link"}
                )
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
                    "group-ongoing-collection/v1",
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
    if not any(
        trace["resource"] == "analyses" and trace["membership"]["value"]
        for trace in traces
    ):
        raise ValueError(
            f"No leading or additional affiliation found for group {profile.group!r}"
        )
    subgroup_buttons = subgroup_button_choices(
        profile.group,
        [name for row in ongoing for name in row.filter_metadata["subgroups"]],
    )
    return GroupView(
        profile,
        tuple(sorted(ongoing, key=lambda row: row.reference)),
        tuple(sorted(review, key=lambda row: row.reference)),
        tuple(traces),
        registry.metadata,
        tuple(subgroup_buttons.value),
        asdict(subgroup_buttons),
    )
