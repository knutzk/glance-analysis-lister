# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Produce Markdown pages for ongoing analyses in the ATLAS top WG."""

import logging
from pathlib import Path

from analysis_lister.glance.enums import PublicationState, SoftwareRelease
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.glance.subgroups import TopGroups

from .. import utils

logger = logging.getLogger(__name__)


def ongoing_analyses(registry: GlanceRegistry, output_dir: Path, last_modified: str):
    """Create a page with ongoing analyses in the ATLAS top WG.

    Args:
        registry: GlanceRegistry object containing all analyses.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.

    """
    logger.debug("Generating ongoing analyses overview.")

    output_file = output_dir / "ongoing.md"
    logger.debug(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_global_counts(_f, registry)
        _write_subgroup_breakdown(_f, registry)
        _write_status_breakdown(_f, registry)
        _write_table(_f, registry)


def _write_header(_f, last_modified: str):
    """Write the header for the ongoing analyses page."""
    _f.write(utils.HIDE_TOC)
    _f.write("# Ongoing analyses\n\n\n")
    _f.write(utils.print_header_timestamp(last_modified))
    _f.write(
        "The following table lists all ongoing analyses in the ATLAS top WG.\n\n"
        '- The "**EB PA A**" column indicates the review status of the analyses:\n'
        "    - One tick mark = EdBoard is assigned (EB),\n"
        "    - two tick marks = analysis is pre-approved (PA),\n"
        "    - three tick marks = analysis is group-approved (A).\n"
        '- The "**Subgroups**" column lists all top WG subgroups involved in the '
        "analysis.\n"
        '- "**Rel.**" shows the software release the analysis uses – it is based '
        "on the keywords assigned to the analysis on GLANCE.\n\n"
    )


def _write_global_counts(_f, registry: GlanceRegistry):
    """Write global counts for ongoing analyses."""
    logger.debug("Writing detailed analysis counts for ongoing analyses.")

    analysis_count = registry.count(lambda a: a.is_ongoing())
    release_counts = {
        r: registry.count(lambda a: a.is_ongoing() and a.software_release == r)
        for r in SoftwareRelease
    }

    _f.write('!!! info "Detailed analysis counts"\n\n')
    _f.write(f"    * **All ongoing analyses**: {analysis_count} (")
    _f.write(f"{release_counts[SoftwareRelease.R21]} analyses in R21, ")
    _f.write(f"{release_counts[SoftwareRelease.R25]} analyses in R25, ")
    _f.write(f"{release_counts[SoftwareRelease.UNKNOWN]} unknown)\n")


def _write_subgroup_breakdown(_f, registry: GlanceRegistry):
    """Write subgroup breakdown for ongoing analyses."""
    logger.debug("Writing subgroup counts for ongoing analyses.")
    _f.write("    * **Split by subgroup** (double-counts possible):\n")

    for g in TopGroups:
        subgroup_total = registry.count(
            lambda a: g.id in a.subgroups and a.is_ongoing()
        )
        subgroup_counts = registry.count_by_state(lambda a: g.id in a.subgroups)
        pre_approved_count = (
            subgroup_counts[PublicationState.PREAPPROVED]
            + subgroup_counts[PublicationState.PHASE1_OR_2]
        )

        _f.write(
            f"        * {g.title}: {subgroup_total} ("
            f"pre-approved: {pre_approved_count}, "
            f"with EdBoard: {subgroup_counts[PublicationState.ONGOING_WITH_EB]}, "
            f"no EdBoard: {subgroup_counts[PublicationState.ONGOING_WO_EB]})\n"
        )


def _write_status_breakdown(_f, registry: GlanceRegistry):
    """Write status breakdown for ongoing analyses."""
    logger.debug("Writing status counts for ongoing analyses.")

    def write_line(state: PublicationState, label: str):
        total = registry.count(lambda a: a.pub_state == state)
        r21 = registry.count(
            lambda a: a.pub_state == state and a.software_release == SoftwareRelease.R21
        )
        r25 = registry.count(
            lambda a: a.pub_state == state and a.software_release == SoftwareRelease.R25
        )
        unknown = registry.count(
            lambda a: (
                a.pub_state == state and a.software_release == SoftwareRelease.UNKNOWN
            )
        )

        _f.write(f"        * {label}: {total} ({r21} analyses in R21, ")
        _f.write(f"{r25} analyses in R25, {unknown} unknown)\n")

    _f.write("    * **Split by status**:\n")
    write_line(PublicationState.PHASE1_OR_2, "Approved")
    write_line(PublicationState.PREAPPROVED, "Pre-approved")
    write_line(PublicationState.ONGOING_WITH_EB, "With EdBoard")
    write_line(PublicationState.ONGOING_WO_EB, "No EdBoard")


def _write_table(_f, registry: GlanceRegistry):
    """Write the main analysis table for ongoing analyses."""
    logger.debug("Writing main analysis table.")
    _f.write("\n\n| Identifier | Title | EB PA A | Subgroups | Rel. | Start |\n")
    _f.write("| --- | --- | --- | --- | --- | --- |\n")

    tickmark = "&#10003;&nbsp;"
    state_to_n_ticks = {
        PublicationState.PHASE1_OR_2: 3,
        PublicationState.PAST_PHASE0: 3,
        PublicationState.PREAPPROVED: 2,
        PublicationState.ONGOING_WITH_EB: 1,
    }

    for a in registry.analyses:
        logger.debug(f"Writing table row for analysis {a.ref_code}.")
        n_ticks = state_to_n_ticks.get(a.pub_state, 0)
        subgroups_str = (
            ", ".join(g.code for g in TopGroups if g.id in a.subgroups) or "None"
        )

        _f.write(
            f"| {utils.render_ref_link(a)} "
            f"| {a.title_short} "
            f"| {tickmark * n_ticks} "
            f"| {subgroups_str} "
            f"| {a.software_release.value} "
            f"| {a.date_start.replace('-', '&#8209;')} "
            f"|\n"
        )
