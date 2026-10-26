# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve explicit links, preserving publication ownership and diagnostics."""

from ..registry.reader import LINK_RESOURCES


def reconcile_relationships(analyses, publications):
    linked = {reference: {} for reference in analyses}
    issues = {reference: [] for reference in analyses}
    for (resource, reference), (record, _, state) in publications.items():
        relation = record.get("relatedAnalysis") or {}
        if (
            relation.get("type") == "Analysis"
            and relation.get("referenceCode") in analyses
        ):
            linked[relation["referenceCode"]][resource, reference] = {
                "resource": resource,
                "reference": reference,
                "state": state.value,
                "relationship": "publication.relatedAnalysis",
            }
    # Reconcile outbound links against publication-owned relationships.
    for reference, record in analyses.items():
        for relation in record.get("relatedPublications") or []:
            resource = LINK_RESOURCES.get(relation.get("type"))
            key = resource, relation.get("referenceCode")
            target = publications.get(key)
            if target is None:
                if record.get("status") != "Closed":
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
    return linked, issues
