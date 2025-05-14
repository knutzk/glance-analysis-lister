import logging
from pathlib import Path
from typing import List

from analysis_lister.glance import subgroups
from analysis_lister.glance.enums import PublicationState, SoftwareRelease
from analysis_lister.glance.analysis import Analysis
from ..render import utils

logger = logging.getLogger(__name__)


def ongoing_analyses(
    list_of_analyses: list[Analysis],
    output_dir: Path,
    last_modified: str,
):
    """Create a page with ongoing analyses for one subgroup.

    Takes a list of analyses and produces a Markdown page with subsections for
    each analysis. The analyses are filtered based on the 'subgroup_id' string
    being part of the 'Subgroups' field in GLANCE. The analyses are listed
    in separate subsectinos depending on their stage in the approval process.

    Parameters:
        list_of_analyses: A list of analysis objects considered for the table.
        output_dir: String for the output directory of the Markdown file.
    """
    logger.info("Generating ongoing analyses overview.")

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

        def provide_counts(alist: List[Analysis], criteria):
            """Provide total count and count per release."""
            filtered = [x for x in alist if criteria(x)]
            f_R21 = sum(x.software_release == SoftwareRelease.R21 for x in filtered)
            f_R25 = sum(x.software_release == SoftwareRelease.R25 for x in filtered)
            return (
                f"{len(filtered)} ({f_R21} analyses in R21, {f_R25} analyses "
                f"in R25, {len(filtered) - f_R21 - f_R25} unknown)"
            )

        logger.info("Writing detailed analysis counts for ongoing analyses.")
        _f.write('!!! info "Detailed analysis counts"\n\n')
        _f.write("    * **All ongoing analyses**: ")
        _f.write(provide_counts(list_of_analyses, lambda _: True))
        _f.write("\n")

        # =====================================================================
        # Split by subgroup
        # =====================================================================
        logger.info("Writing subgroup counts for ongoing analyses.")
        _f.write("    * **Split by subgroup** (double-counts possible):\n")
        for g in subgroups.TopGroups:
            count = sum(g.id in x.subgroups for x in list_of_analyses)
            _f.write(f"        * {g.title}: {count} (")
            count = sum(
                1
                for x in list_of_analyses
                if g.id in x.subgroups
                and x.pub_state
                in [PublicationState.PREAPPROVED, PublicationState.PHASE1_OR_2]
            )
            _f.write(f"pre-approved: {count}, ")
            count = sum(
                1
                for x in list_of_analyses
                if g.id in x.subgroups
                and x.pub_state == PublicationState.ONGOING_WITH_EB
            )
            _f.write(f"with EdBoard: {count}, ")
            count = sum(
                1
                for x in list_of_analyses
                if g.id in x.subgroups and x.pub_state == PublicationState.ONGOING_WO_EB
            )
            _f.write(f"no EdBoard: {count})\n")

        # =====================================================================
        # Split by status
        # =====================================================================
        logger.info("Writing status counts for ongoing analyses.")
        _f.write("    * **Split by status**:\n")
        _f.write("        * Approved: ")
        _f.write(
            provide_counts(
                list_of_analyses,
                lambda x: x.pub_state == PublicationState.PHASE1_OR_2,
            )
        )
        _f.write("\n        * Pre-approved: ")
        _f.write(
            provide_counts(
                list_of_analyses,
                lambda x: x.pub_state == PublicationState.PREAPPROVED,
            )
        )
        _f.write("\n        * With EdBoard: ")
        _f.write(
            provide_counts(
                list_of_analyses,
                lambda x: x.pub_state == PublicationState.ONGOING_WITH_EB,
            )
        )
        _f.write("\n        * No EdBoard: ")
        _f.write(
            provide_counts(
                list_of_analyses,
                lambda x: x.pub_state == PublicationState.ONGOING_WO_EB,
            )
        )
        _f.write("\n\n\n")

        _f.write("| Identifier | Title | EB PA A | Subgroups | Rel. | Start |\n")
        _f.write("| --- | --- | --- | --- | --- | --- |\n")

        for a in list_of_analyses:
            logger.debug(f"Writing table row for analysis {a.ref_code}.")

            tickmark = "&#10003;&nbsp;"
            state_to_n_ticks = {
                PublicationState.PAST_PHASE0: 3,
                PublicationState.PREAPPROVED: 2,
                PublicationState.ONGOING_WITH_EB: 1,
            }
            n_ticks = state_to_n_ticks.get(a.pub_state, 0)

            def _get_top_subgroup_codes(grps: List[str]) -> str:
                """Get the top subgroup codes from a list of subgroup codes."""
                top_subgroups = [g.code for g in subgroups.TopGroups if g.id in grps]
                return ", ".join(top_subgroups) if top_subgroups else "None"

            _f.write(
                f'| [{a.ref_code.replace("-", "&#8209;")}][{a.ref_code}] '
                f"| {a.title_short} "
                f"| {tickmark * n_ticks} "
                f"| {_get_top_subgroup_codes(a.subgroups)} "
                f"| {a.software_release.value} "
                f'| {a.date_start.replace("-", "&#8209;")} '
                f"|\n",
            )
