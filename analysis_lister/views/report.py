# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Scope and serialize provenance for one group's prepared collections."""

from collections import Counter
from hashlib import sha256
from pathlib import Path

from attrs import asdict

from ..registry.reader import LINK_RESOURCES
from .curation import archive_curation_statement


def build_report(view, snapshot, raw):
    profile = view.profile
    policy = profile.publication_policy
    relevant = [
        trace
        for trace in view.decisions
        if (trace.get("curation") or trace["membership"])["value"]
    ]
    issues = sum(
        bool(
            trace.get("relationship_issues")
            or trace.get("relationship_issue")
            or trace["state"]["value"] == "unknown"
        )
        for trace in relevant
    )
    counts = {
        "ongoing_analyses": len(view.ongoing),
        "analyses_needing_review": len(view.needs_review),
        "records_with_diagnostics": issues,
        "publication_records": len(view.publications),
        "archive_publications": len(view.archive),
    }
    # Reports travel with one group's pages: retain its records and the explicit
    # relationship targets needed to explain decisions, rather than the full snapshot.
    context = {(trace["resource"], trace["reference"]) for trace in relevant}
    for trace in relevant:
        if trace["resource"] == "analyses":
            for issue in trace.get("relationship_issues", []):
                relation = issue["link"]
                context.add(
                    (
                        LINK_RESOURCES.get(relation.get("type")),
                        relation.get("referenceCode"),
                    )
                )
            for link in trace["state"]["inputs"]["linked_publication_states"]:
                context.add((link["resource"], link["reference"]))
        else:
            relation = trace.get("relatedAnalysis") or {}
            if relation.get("type") == "Analysis":
                context.add(("analyses", relation.get("referenceCode")))
    decisions = [
        trace
        for trace in view.decisions
        if (trace["resource"], trace["reference"]) in context
    ]
    report = {
        "schema": "glance-group-view-report",
        "schema_version": 2,
        "snapshot": {
            "filename": Path(snapshot).name,
            "sha256": sha256(raw).hexdigest(),
        },
        "profile": asdict(profile),
        "source_metadata": view.source_metadata,
        "policy": {
            "group": "ongoing analyses always use main-group affiliation; all archive publication types use the separately recorded archive-curation rule",
            "publication_affiliation": "direct; linked-analysis fallback only when main-group assignment is absent",
            "relationships": "publication-owned links take precedence over contradictory analysis-owned links; one-way links are reported",
            "ongoing": "one row per native analysis identifier; a recognised active review state is required",
            "history": "no year cutoff; completed superseded notes retained",
            "archive_curation": archive_curation_statement(profile),
            "clones": "no legacy lookup or title-based clone exclusions applied",
        },
        "counts": counts,
        "publication_filters": view.publication_filters,
        "subgroup_buttons": view.subgroup_button_provenance,
        "publication_states": {
            resource: dict(
                Counter(
                    row.state for row in view.publications if row.resource == resource
                )
            )
            for resource in ("papers", "confnotes", "pubnotes")
        },
        "decisions": decisions,
        "report_scope": {
            "description": "affiliated records and their explicit one-hop relationship context",
            "other_records_omitted": dict(
                Counter(
                    trace["resource"]
                    for trace in view.decisions
                    if (trace["resource"], trace["reference"]) not in context
                )
            ),
        },
    }
    report["archive_keyword_policy"] = {
        "rule": "archive-configured-curation",
        "keywords": list(policy.keywords) if policy else [],
        "groups": list(policy.groups) if policy else None,
        "subgroups": list(policy.subgroups) if policy else [],
        "matching": "exact case-insensitive keyword equality",
    }
    return report
