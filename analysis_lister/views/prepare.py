# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Assemble independent prepared collections without rendering or I/O."""

from attrs import asdict

from .analyses import prepare_analyses
from .common import subgroup_button_choices
from .models import GroupView
from .publications import prepare_publications
from .relationships import reconcile_relationships


def prepare_group(registry, profile):
    analyses = {row["referenceCode"]: row for row in registry.records("analyses")}
    publications, traces = prepare_publications(registry, profile, analyses)
    linked, issues = reconcile_relationships(analyses, publications)
    ongoing, review, analysis_traces = prepare_analyses(
        analyses, publications, linked, issues, profile
    )
    traces.extend(analysis_traces)
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
