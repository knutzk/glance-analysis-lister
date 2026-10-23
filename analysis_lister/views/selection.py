# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Select group collections once, retaining the reasons behind every decision."""

from attrs import asdict

from ..registry.reader import LINK_RESOURCES
from ..registry.schema import record_key
from .curation import archive_curation
from .models import AnalysisRow, Decision, GroupView, PublicationRow
from .semantics import (
    ONGOING,
    analysis_email_lists,
    analysis_review_order,
    analysis_state,
    approval_progress,
    associated_paper_statuses,
    group_membership,
    iso_date,
    last_milestone,
    last_paper_milestone,
    publication_details,
    publication_filter_values,
    publication_leading_subgroup,
    publication_state,
    publication_subgroups,
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
            phase = (
                record.get("publicationPhase") or {}
                if resource == "papers"
                else record.get("phase1") or {}
            )
            date_field = (
                "publishedOnlineDate" if resource == "papers" else "releaseDate"
            )
            day = iso_date(phase.get(date_field))
            subgroup_decision = publication_subgroups(record, related)
            leading_subgroup = publication_leading_subgroup(record, related)
            metadata_decisions = {
                key: publication_filter_values(record, related, field)
                for key, field in (
                    ("keywords", "gal_keywords"),
                    ("triggers", "gal_triggers"),
                    ("statistical_tools", "gal_statisticalTools"),
                )
            }
            details = publication_details(record, resource, related)
            affiliation_evidence = Decision(
                "publication-affiliations/v1",
                details.value["groups"],
                "publication main-group assignment; explicit linked-analysis fallback when no main groups are recorded",
                {
                    key: value
                    for key, value in details.inputs.items()
                    if key
                    in {"gal_groups", "relatedAnalysis", "relatedAnalysis.gal_groups"}
                },
            )
            curation = archive_curation(
                reference,
                profile,
                metadata_decisions["keywords"],
                affiliation_evidence,
                subgroup_decision,
            )
            keywords = metadata_decisions["keywords"].value
            dois = (record.get("publicationPhase") or {}).get("gal_dois") or []
            citations = tuple(
                entry.get("citation") or entry.get("doi", "") for entry in dois
            )
            if resource == "papers":
                metadata_decisions["publication_status"] = Decision(
                    "paper-doi-status/v1",
                    "published"
                    if any(entry.get("doi") for entry in dois)
                    else "under-review",
                    "published means at least one cached DOI; archived papers without a DOI are under review",
                    {"publicationPhase.gal_dois": dois},
                )
            people_sources = {
                "gal_analysisContacts": record.get("gal_analysisContacts"),
                "gal_contactEditors": record.get("gal_contactEditors"),
                "gal_internalNoteEditors": record.get("gal_internalNoteEditors"),
                **{
                    "phase1." + key: (record.get("phase1") or {}).get(key)
                    for key in (
                        "gal_editorialBoard",
                        "gal_editorialBoardChairs",
                        "gal_editorialBoardExOfficio",
                        "gal_firstSignOffResponsible",
                        "gal_secondSignOffResponsible",
                        "gal_readers",
                        "gal_firstReaders",
                        "gal_secondReaders",
                    )
                },
            }
            people = list(
                dict.fromkeys(
                    name
                    for value in people_sources.values()
                    for name in ([value] if isinstance(value, str) else value or [])
                    if isinstance(name, str) and name.strip()
                )
            )
            metadata_decisions["people"] = Decision(
                "publication-search-people/v2",
                people,
                "recorded publication contacts, editors, editorial board, readers and sign-off responsible names; no inferred people",
                people_sources,
            )
            label = (
                record.get("finalReferenceCode")
                or record.get("gal_finalReferenceCode")
                or reference
            )
            title = record.get("shortTitle") or reference
            filters = {
                "publication_type": resource,
                "leading_subgroup": leading_subgroup.value,
                **{key: decision.value for key, decision in metadata_decisions.items()},
                "subgroups": subgroup_decision.value,
                "state": state.value,
                "text": " ".join(
                    [
                        reference,
                        label,
                        title,
                        *citations,
                        *metadata_decisions["people"].value,
                        *(
                            [entry.get("doi") or "" for entry in dois]
                            if resource == "papers"
                            else [details.value.get("cds_url") or ""]
                        ),
                        *subgroup_decision.value,
                        *keywords,
                        *metadata_decisions["triggers"].value,
                        *metadata_decisions["statistical_tools"].value,
                    ]
                ),
            }
            date_decision = Decision(
                "publication-calendar-date/v2",
                day,
                "ISO calendar date without timezone conversion; absent or invalid dates remain null",
                {
                    ("publicationPhase." if resource == "papers" else "phase1.")
                    + date_field: phase.get(date_field)
                },
            )
            citation_decision = Decision(
                "publication-citation-text/v1",
                list(citations),
                "cached citation text, falling back to the DOI; no external lookup",
                {"publicationPhase.gal_dois": dois},
            )
            row = PublicationRow(
                resource,
                reference,
                label,
                title,
                state.value,
                day,
                tuple(subgroup_decision.value),
                citations,
                filters,
                {
                    "membership": asdict(membership),
                    "curation": asdict(curation),
                    "subgroups": asdict(subgroup_decision),
                    "leading_subgroup": asdict(leading_subgroup),
                    "filter_metadata": {
                        key: asdict(decision)
                        for key, decision in metadata_decisions.items()
                    },
                    "state": asdict(state),
                    "date": asdict(date_decision),
                    "citation": asdict(citation_decision),
                    "details": asdict(details),
                },
                details.value,
            )
            publications[resource, reference] = (record, row, state)
            traces.append(
                {
                    "resource": resource,
                    "reference": reference,
                    "membership": asdict(membership),
                    "curation": asdict(curation),
                    "subgroups": asdict(subgroup_decision),
                    "leading_subgroup": asdict(leading_subgroup),
                    "filter_metadata": {
                        key: asdict(decision)
                        for key, decision in metadata_decisions.items()
                    },
                    "state": asdict(state),
                    "date": asdict(date_decision),
                    "citation": asdict(citation_decision),
                    "details": asdict(details),
                    "inclusion": asdict(
                        Decision(
                            "group-publication-collection/v1",
                            curation.value,
                            "curated publication records; no year cutoff",
                            {"curation": curation.value},
                        )
                    ),
                    "archive_inclusion": asdict(
                        Decision(
                            "group-publication-archive/v1",
                            curation.value
                            and state.value in {"submitted", "published", "released"},
                            "curated submitted/published paper or released note; all years and historical superseded releases retained",
                            {"curation": curation.value, "state": state.value},
                        )
                    ),
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
                    "state": target[2].value,
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
    included_keys = {
        (trace["resource"], trace["reference"])
        for trace in traces
        if trace["resource"] != "analyses" and trace["inclusion"]["value"]
    }
    selected = tuple(
        value[1] for key, value in publications.items() if key in included_keys
    )
    if not any(
        (trace.get("curation") or trace["membership"])["value"] for trace in traces
    ):
        raise ValueError(
            f"No leading or additional affiliation found for group {profile.group!r}"
        )
    recent = sorted(
        (
            row
            for row in selected
            if row.state in {"published", "released"} and row.date
        ),
        key=lambda row: (row.date, row.resource, row.reference),
        reverse=True,
    )[: profile.recent_limit]
    subgroup_buttons = subgroup_button_choices(
        profile.group,
        [
            name
            for row in [*ongoing, *selected]
            for name in row.filter_metadata["subgroups"]
        ],
    )
    return GroupView(
        profile,
        tuple(sorted(ongoing, key=lambda row: row.reference)),
        tuple(sorted(review, key=lambda row: row.reference)),
        selected,
        tuple(recent),
        tuple(traces),
        registry.metadata,
        {
            "between_categories": "and",
            "within_categories": "or",
            "subgroups": sorted({name for row in selected for name in row.subgroups}),
            "publication_type": [
                resource
                for resource in ("papers", "confnotes", "pubnotes")
                if any(row.resource == resource for row in selected)
            ],
            "subgroup_assignment": "current snapshot",
            "triggers": sorted(
                {value for row in selected for value in row.filter_metadata["triggers"]}
            ),
            "statistical_tools": sorted(
                {
                    value
                    for row in selected
                    for value in row.filter_metadata["statistical_tools"]
                }
            ),
            "leading_subgroup": sorted(
                {
                    row.filter_metadata["leading_subgroup"]
                    for row in selected
                    if row.filter_metadata["leading_subgroup"]
                }
            ),
            "keywords": sorted(
                {value for row in selected for value in row.filter_metadata["keywords"]}
            ),
        },
        tuple(subgroup_buttons.value),
        asdict(subgroup_buttons),
    )
