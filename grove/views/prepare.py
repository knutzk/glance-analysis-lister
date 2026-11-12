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
    subgroup_buttons = subgroup_button_choices(
        profile.group,
        [name for row in ongoing for name in row.metadata["subgroups"]],
    )
    controls = {
        "within_categories": "or",
        "between_categories": "and",
        "ongoing": {
            "subgroups": tuple(subgroup_buttons.value),
            "sort": (
                ("stage-desc", "Review stage: most advanced first"),
                ("stage-asc", "Review stage: earliest first"),
                ("reference", "Analysis identifier"),
            ),
        },
        "papers": {
            "publication_status": (
                ("published", "Published"),
                ("under-review", "Under review"),
            ),
        },
        "confnotes": {
            "supersession": (
                ("non-superseded", "Non-superseded"),
                ("superseded", "Superseded"),
            ),
        },
        "pubnotes": {
            "supersession": (
                ("non-superseded", "Non-superseded"),
                ("superseded", "Superseded"),
            ),
        },
    }
    return GroupView(
        profile,
        tuple(sorted(ongoing, key=lambda row: row.reference)),
        tuple(sorted(review, key=lambda row: row.reference)),
        selected,
        tuple(traces),
        registry.metadata,
        controls,
        asdict(subgroup_buttons),
    )
