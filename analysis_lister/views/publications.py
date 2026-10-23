# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publications preparation and traceable interpretation of curated records."""

import re

from attrs import asdict

from ..registry.schema import record_key
from .common import group_membership, iso_date
from .curation import archive_curation
from .models import Decision, PublicationDetails, PublicationRow
from .notes import note_cds_record, note_expansion


def publication_subgroups(record, related):
    """Current-snapshot labels; an explicit analysis link supplies missing labels."""

    def labels(value):
        groups = value.get("gal_groups") or {}
        return list(
            dict.fromkeys(
                name
                for name in [
                    groups.get("leadingSubgroup"),
                    *(groups.get("subgroups") or []),
                ]
                if name
            )
        )

    direct = labels(record)
    inputs = {
        "gal_groups.leadingSubgroup": (record.get("gal_groups") or {}).get(
            "leadingSubgroup"
        ),
        "gal_groups.subgroups": (record.get("gal_groups") or {}).get("subgroups", []),
    }
    reason = "subgroup assignments recorded on the publication in the current snapshot"
    value = direct
    if not direct and related is not None:
        value = labels(related)
        inputs.update(
            {
                "relatedAnalysis": record.get("relatedAnalysis"),
                "analysis.gal_groups": related.get("gal_groups"),
            }
        )
        reason = "missing publication subgroups inherited through its explicit analysis link; current snapshot assignments"
    return Decision("publication-current-subgroups/v1", value, reason, inputs)


def publication_leading_subgroup(record, related):
    value = (record.get("gal_groups") or {}).get("leadingSubgroup")
    inputs = {"gal_groups.leadingSubgroup": value}
    reason = "leading subgroup recorded on the publication in the current snapshot"
    if not value and related is not None:
        value = (related.get("gal_groups") or {}).get("leadingSubgroup")
        inputs.update(
            {
                "relatedAnalysis": record.get("relatedAnalysis"),
                "analysis.gal_groups.leadingSubgroup": value,
            }
        )
        reason = "missing leading subgroup inherited through the explicit analysis link; current snapshot assignment"
    return Decision("publication-leading-subgroup/v1", value or None, reason, inputs)


def publication_filter_values(record, related, field):
    path = "metadata." + field
    values = (record.get("metadata") or {}).get(field) or []
    inputs = {path: values}
    reason = "values recorded on the publication"
    if not values and related is not None:
        values = (related.get("metadata") or {}).get(field) or []
        inputs.update(
            {
                "relatedAnalysis": record.get("relatedAnalysis"),
                "analysis." + path: values,
            }
        )
        reason = (
            "missing values inherited through the explicit analysis link"
            if values
            else "no values recorded on the publication or linked analysis"
        )
    return Decision(
        "publication-filter-metadata/v1", list(dict.fromkeys(values)), reason, inputs
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


def publication_details(record, resource, related=None):
    """Prepare publication-owned people and links without legacy models or requests."""
    phase = record.get("phase1") or {}
    publication = record.get("publicationPhase") or {}
    sources = {
        "gal_analysisContacts": record.get("gal_analysisContacts") or [],
        "gal_contactEditors": record.get("gal_contactEditors") or [],
        "phase1.gal_editorialBoard": phase.get("gal_editorialBoard") or [],
        "gal_groups": record.get("gal_groups") or {},
        "gal_figuresUrl": record.get("gal_figuresUrl"),
        "phase1.publicWebPageUrlForFiguresAndTables": phase.get(
            "publicWebPageUrlForFiguresAndTables"
        ),
        "publicationPhase.arXivUrls": publication.get("arXivUrls") or [],
        "publicationPhase.gal_dois": publication.get("gal_dois") or [],
        "documentation.supportingInternalDocuments": (
            record.get("documentation") or {}
        ).get("supportingInternalDocuments")
        or [],
    }
    groups = sources["gal_groups"]
    if (
        not groups.get("leadingGroup")
        and not groups.get("otherGroups")
        and related is not None
    ):
        groups = related.get("gal_groups") or {}
        sources["relatedAnalysis"] = record.get("relatedAnalysis")
        sources["relatedAnalysis.gal_groups"] = groups
    links = []
    public_url = (
        sources["gal_figuresUrl"]
        or sources["phase1.publicWebPageUrlForFiguresAndTables"]
    )
    if public_url:
        links.append({"label": "Public page", "url": public_url})
    for source, label in (
        ("publicationPhase.arXivUrls", "arXiv"),
        ("publicationPhase.gal_dois", "DOI"),
        ("documentation.supportingInternalDocuments", "Supporting document"),
    ):
        for item in sources[source]:
            if isinstance(item, dict):
                links.append(
                    {
                        "label": item.get("label") or label,
                        "url": item.get("url")
                        or (
                            "https://doi.org/" + item["doi"]
                            if item.get("doi")
                            else None
                        ),
                    }
                )
    publication_records = []
    for item in sources["publicationPhase.arXivUrls"]:
        if isinstance(item, dict) and item.get("url"):
            publication_records.append({"label": "arXiv", "url": item["url"]})
    for item in sources["publicationPhase.gal_dois"]:
        if isinstance(item, dict):
            url = item.get("url") or (
                "https://doi.org/" + item["doi"] if item.get("doi") else None
            )
            if url:
                publication_records.append(
                    {
                        "label": item.get("citation") or item.get("doi") or "DOI",
                        "url": url,
                    }
                )
    is_note = resource in {"confnotes", "pubnotes"}
    cds_record = note_cds_record(record, resource) if is_note else None
    conf_details = note_expansion(record, resource) if is_note else None
    if cds_record is not None:
        sources["cds_record"] = asdict(cds_record)
        sources[
            "conf_note_expansion" if resource == "confnotes" else "pub_note_expansion"
        ] = asdict(conf_details)
    milestone = last_paper_milestone(record) if resource == "papers" else None
    if milestone is not None:
        sources["last_paper_milestone"] = asdict(milestone)
    return Decision(
        "publication-details/v3",
        {
            "last_milestone": milestone.value if milestone else None,
            "publication_records": publication_records,
            "contacts": sources["gal_analysisContacts"],
            "editors": sources["gal_contactEditors"],
            "board": sources["phase1.gal_editorialBoard"],
            "groups": groups,
            "links": links,
            "cds_url": cds_record.value if cds_record else None,
            "conf_note": conf_details.value if resource == "confnotes" else None,
            "pub_note": conf_details.value if resource == "pubnotes" else None,
        },
        "people and links recorded directly on the publication; missing main groups use the explicitly linked analysis affiliation; no inferred people or external requests",
        sources,
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


def prepare_publications(registry, profile, analyses):
    publications, traces = {}, []
    for resource in ("papers", "confnotes", "pubnotes"):
        for record in registry.records(resource):
            reference = record_key(record, resource)
            state = publication_state(record, resource)
            membership = group_membership(record, profile.group)
            relation = record.get("relatedAnalysis")
            related = None
            if isinstance(relation, dict) and relation.get("type") == "Analysis":
                related = analyses.get(relation.get("referenceCode"))
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
                PublicationDetails.from_evidence(details.value),
            )
            publications[resource, reference] = (record, row, state)
            traces.append(
                {
                    "resource": resource,
                    "reference": reference,
                    **row.provenance,
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
    return publications, traces
