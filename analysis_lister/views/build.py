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
from .markdown.pages import ongoing_page
from .selection import prepare_group
from .writer import write_documents

logger = logging.getLogger(__name__)


def render_group(snapshot, output_dir, profile):
    raw = Path(snapshot).read_bytes()
    registry = CuratedRegistry(json.loads(raw))
    view = prepare_group(registry, profile)
    relevant = [trace for trace in view.decisions if trace["membership"]["value"]]
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
            "group": "leading or additional main group; subgroup membership does not select records",
            "publication_affiliation": "direct; linked-analysis fallback only when main-group assignment is absent",
            "relationships": "publication-owned links take precedence over contradictory analysis-owned links; one-way links are reported",
            "ongoing": "one row per native analysis identifier; a recognised active review state is required",
            "clones": "no legacy lookup or title-based clone exclusions applied",
        },
        "counts": counts,
        "subgroup_buttons": view.subgroup_button_provenance,
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
    documents = {
        "ongoing.md": ongoing_page(view),
        "view-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    for name in ("gal-views.css", "gal-views.js"):
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
