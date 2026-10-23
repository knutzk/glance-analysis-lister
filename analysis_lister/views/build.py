# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build group pages and a derivation report from one immutable input snapshot."""

import json
import logging
from collections import Counter
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from attrs import asdict

from ..registry import CuratedRegistry
from ..registry.reader import LINK_RESOURCES
from .curation import archive_curation_statement
from .markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from .selection import prepare_group
from .writer import write_documents

logger = logging.getLogger(__name__)


def render_group(snapshot, output_dir, profile):
    if profile.archive_groups is None:
        print(
            f"WARNING: No publication curation configuration for {profile.group}; using only its internal identifier group token."
        )
    raw = Path(snapshot).read_bytes()
    registry = CuratedRegistry(json.loads(raw))
    view = prepare_group(registry, profile)
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
        "schema_version": 1,
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
        "rule": "archive-configured-curation/v3",
        "keywords": list(profile.archive_keywords),
        "groups": list(profile.archive_groups)
        if profile.archive_groups is not None
        else None,
        "subgroups": list(profile.archive_subgroups),
        "matching": "exact case-insensitive keyword equality",
    }
    documents = {
        "ongoing.md": ongoing_page(view),
        "papers.md": papers_page(view),
        "confnotes.md": confnotes_page(view),
        "pubnotes.md": pubnotes_page(view),
        "view-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    for name in (
        "gal-views.css",
        "gal-views.js",
        "gal-publications.css",
        "gal-publications.js",
        "gal-confnotes.css",
        "gal-confnotes.js",
    ):
        documents["assets/" + name] = (
            files("analysis_lister.views")
            .joinpath("assets", name)
            .read_text(encoding="utf-8")
        )
    write_documents(output_dir, documents, snapshot=snapshot)
    if issues:
        logger.warning(
            "%d affiliated records have state or relationship diagnostics; inspect view-report.json",
            issues,
        )
    return counts
