import logging
from pathlib import Path
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.enums import PublicationState, SoftwareRelease
from analysis_lister.glance.subgroups import TopGroups
from ..render import utils

logger = logging.getLogger(__name__)


def ongoing_analyses(
    registry: GlanceRegistry,
    output_dir: Path,
    last_modified: str,
):
    """Create a page with ongoing analyses in the ATLAS top WG.

    Parameters:
        registry: GlanceRegistry instance with loaded and filtered data.
        output_dir: Path to write the Markdown output.
        last_modified: Timestamp string for the sync header.
    """
    logger.info("Generating ongoing analyses overview.")
    analyses = registry.analyses

    output_file = output_dir / "ongoing.md"
    logger.info(f'Writing output file "{output_file}"')

    with open(output_file, "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
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

        n_ongoing = len(analyses)
        n_ongoing_r21 = len(
            [a for a in analyses if a.software_release == SoftwareRelease.R21]
        )
        n_ongoing_r25 = len(
            [a for a in analyses if a.software_release == SoftwareRelease.R25]
        )
        n_ongoing_unknown = len(
            [a for a in analyses if a.software_release == SoftwareRelease.UNKNOWN]
        )

        logger.info("Writing detailed analysis counts for ongoing analyses.")
        _f.write('!!! info "Detailed analysis counts"\n\n')
        _f.write("    * **All ongoing analyses**: ")
        _f.write(f"{n_ongoing} ({n_ongoing_r21} analyses in R21, ")
        _f.write(f"{n_ongoing_r25} analyses in R25, {n_ongoing_unknown} unknown)\n")

        # =====================================================================
        # Split by subgroup
        # =====================================================================
        logger.info("Writing subgroup counts for ongoing analyses.")
        _f.write("    * **Split by subgroup** (double-counts possible):\n")
        for g in TopGroups:
            subgroup_total = registry.count(
                lambda a: g.id in a.subgroups and a.is_ongoing()
            )
            subgroup_counts = registry.count_by_state(lambda a: g.id in a.subgroups)
            _f.write(
                f"        * {g.title}: {subgroup_total} ("
                f"pre-approved: {subgroup_counts[PublicationState.PREAPPROVED] + subgroup_counts[PublicationState.PHASE1_OR_2]}, "
                f"with EdBoard: {subgroup_counts[PublicationState.ONGOING_WITH_EB]}, "
                f"no EdBoard: {subgroup_counts[PublicationState.ONGOING_WO_EB]})\n"
            )

        counts_by_state = registry.count_by_state(lambda a: isinstance(a, Analysis))
        counts_by_state_R21 = registry.count_by_state(
            lambda a: isinstance(a, Analysis)
            and a.software_release == SoftwareRelease.R21
        )
        counts_by_state_R25 = registry.count_by_state(
            lambda a: isinstance(a, Analysis)
            and a.software_release == SoftwareRelease.R25
        )
        counts_by_state_unknown = registry.count_by_state(
            lambda a: isinstance(a, Analysis)
            and a.software_release == SoftwareRelease.UNKNOWN
        )

        _f.write("    * **Split by status**:\n")
        _f.write("        * Approved: ")
        _f.write(f"{counts_by_state[PublicationState.PHASE1_OR_2]} ")
        _f.write(
            f"({counts_by_state_R21[PublicationState.PHASE1_OR_2]} analyses in R21, "
        )
        _f.write(
            f"{counts_by_state_R25[PublicationState.PHASE1_OR_2]} analyses in R25, "
        )
        _f.write(f"{counts_by_state_unknown[PublicationState.PHASE1_OR_2]} unknown)\n")
        _f.write("        * Pre-approved: ")
        _f.write(f"{counts_by_state[PublicationState.PREAPPROVED]} ")
        _f.write(
            f"({counts_by_state_R21[PublicationState.PREAPPROVED]} analyses in R21, "
        )
        _f.write(
            f"{counts_by_state_R25[PublicationState.PREAPPROVED]} analyses in R25, "
        )
        _f.write(f"{counts_by_state_unknown[PublicationState.PREAPPROVED]} unknown)\n")
        _f.write("        * With EdBoard: ")
        _f.write(f"{counts_by_state[PublicationState.ONGOING_WITH_EB]} ")
        _f.write(
            f"({counts_by_state_R21[PublicationState.ONGOING_WITH_EB]} analyses in R21, "
        )
        _f.write(
            f"{counts_by_state_R25[PublicationState.ONGOING_WITH_EB]} analyses in R25, "
        )
        _f.write(
            f"{counts_by_state_unknown[PublicationState.ONGOING_WITH_EB]} unknown)\n"
        )
        _f.write("        * No EdBoard: ")
        _f.write(f"{counts_by_state[PublicationState.ONGOING_WO_EB]} ")
        _f.write(
            f"({counts_by_state_R21[PublicationState.ONGOING_WO_EB]} analyses in R21, "
        )
        _f.write(
            f"{counts_by_state_R25[PublicationState.ONGOING_WO_EB]} analyses in R25, "
        )
        _f.write(
            f"{counts_by_state_unknown[PublicationState.ONGOING_WO_EB]} unknown)\n"
        )

        _f.write("\n\n")
        _f.write("| Identifier | Title | EB PA A | Subgroups | Rel. | Start |\n")
        _f.write("| --- | --- | --- | --- | --- | --- |\n")

        tickmark = "&#10003;&nbsp;"
        state_to_n_ticks = {
            PublicationState.PAST_PHASE0: 3,
            PublicationState.PREAPPROVED: 2,
            PublicationState.ONGOING_WITH_EB: 1,
        }

        for a in analyses:
            logger.debug(f"Writing table row for analysis {a.ref_code}.")
            n_ticks = state_to_n_ticks.get(a.pub_state, 0)
            subgroups_str = (
                ", ".join(g.code for g in TopGroups if g.id in a.subgroups) or "None"
            )
            _f.write(
                f"| [{a.ref_code.replace('-', '&#8209;')}][{a.ref_code}] "
                f"| {a.title_short} "
                f"| {tickmark * n_ticks} "
                f"| {subgroups_str} "
                f"| {a.software_release.value} "
                f"| {a.date_start.replace('-', '&#8209;')} "
                f"|\n"
            )
