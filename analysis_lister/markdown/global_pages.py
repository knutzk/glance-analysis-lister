"""Create global overview pages in Markdown for the entire top WG.


"""

from typing import List
import logging
from pathlib import Path
from analysis_lister.glance import analysis, paper, subgroups
from analysis_lister.glance.enums import PublicationState
from . import utils

# Set up logging
logger = logging.getLogger(__name__)


def published(
    list_of_papers: list[paper.Paper],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a list of submitted and published papers.

    Parameters:
        list_of_papers: A list of paper objects considered for the tables.
        output_dir: String for the output directory of the Markdown file.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    logger.info("Generating published papers overview.")

    n_published = sum(x.pub_state == PublicationState.PUBLISHED for x in list_of_papers)
    n_submitted = sum(
        x.pub_state == PublicationState.SUBMITTED_TO_JOURNAL for x in list_of_papers
    )

    logger.debug(f"Found {n_published} published and {n_submitted} submitted papers.")

    output_file = output_dir / "published.md"
    logger.info(f'Writing output file "{output_file}"')

    with open(output_file, "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write("# Submitted/published papers\n\n")

        _f.write(utils.print_header_timestamp(last_modified))

        link = "https://twiki.cern.ch/twiki/bin/view/AtlasPublic/TopPublicResults"
        _f.write(
            f"There are currently {n_submitted} submitted papers for which "
            "one or more of the ATLAS top WG subgroups is listed as the "
            "leading or an additional subgroup.\n"
            f"In addition, {n_published} papers have been published since "
            f"{threshold}.\n\n"
            "These and older publications are also listed on the "
            f"[TopPublicResults twiki page]({link}).\n\n"
        )

        logger.info("Writing detailed paper counts for published papers.")
        _f.write(f'!!! info "Counts per subgroup (since {threshold})"\n\n')
        for g in subgroups.TopGroups:
            count = sum(g.id in x.subgroups for x in list_of_papers)
            _f.write(f"    * {g.title}: {count} (")
            count = sum(
                1
                for x in list_of_papers
                if g.id in x.subgroups and x.pub_state == PublicationState.PUBLISHED
            )
            _f.write(f"published: {count}, ")
            count = sum(
                1
                for x in list_of_papers
                if g.id in x.subgroups
                and x.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
            )
            _f.write(f"submitted: {count})\n")

        _f.write("\n\n")

        _f.write("| Identifier | Title | Subgroup | Submission | Publication |\n")
        _f.write("| --- | --- | --- | --- | --- |\n")

        def _get_top_subgroup_codes(grps: List[str]) -> str:
            """Get the top subgroup codes from a list of subgroup codes."""
            top_subgroups = [
                g.code for g in subgroups.TopGroups if g.id in grps
            ]
            return ", ".join(top_subgroups) if top_subgroups else "None"

        for p in list_of_papers:
            logger.debug(f"Writing table row for paper {p.ref_code}.")
            _f.write(
                f'| [{p.ref_code.replace("-", "&#8209;")}][{p.ref_code}] '
                f"| {p.title_short} "
                f'| {_get_top_subgroup_codes(p.subgroups)} '
                f'| {p.date_submission.replace("-", "&#8209;")} '
                f'| {p.date_publication.replace("-", "&#8209;")} '
                f"|\n",
            )


def ongoing_analyses(
    list_of_analyses: list[analysis.Analysis],
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

        def provide_counts(alist: List[analysis.Analysis], criteria: bool):
            """Provide total count and count per release.

            Parameters:
                alist: The list of analyses to consider.
                criteria: The criteria to apply for filtering.

            Returns: String with analysis counts fulfilling these criteria
                (total count, count in R21, count in R25, unknown).

            """
            filtered = [x for x in alist if criteria(x)]
            f_R21 = sum(1 for x in filtered if "R21" in x.keywords)
            f_R25 = sum(1 for x in filtered if "R22" in x.keywords)
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
                in [
                    PublicationState.PREAPPROVED,
                    PublicationState.PHASE1_OR_2,
                ]
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
                if g.id in x.subgroups
                and x.pub_state == PublicationState.ONGOING_WO_EB
            )
            _f.write(f"no EdBoard: {count})\n")

        # =====================================================================
        # Split by status
        # =====================================================================
        logger.info("Writing status counts for ongoing analyses.")
        _f.write("    * **Split by status**:")
        _f.write("\n        * Approved: ")
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
            release_str = ""
            if "R22" in a.keywords:
                release_str = "R25"
            elif "R21" in a.keywords:
                release_str = "R21"

            tickmark = "&#10003;&nbsp;"
            state_to_n_ticks = {
                PublicationState.PAST_PHASE0: 3,
                PublicationState.PREAPPROVED: 2,
                PublicationState.ONGOING_WITH_EB: 1,
            }
            n_ticks = state_to_n_ticks.get(a.pub_state, 0)

            def _get_top_subgroup_codes(grps: List[str]) -> str:
                """Get the top subgroup codes from a list of subgroup codes."""
                top_subgroups = [
                    g.code for g in subgroups.TopGroups if g.id in grps
                ]
                return ", ".join(top_subgroups) if top_subgroups else "None"

            _f.write(
                f'| [{a.ref_code.replace("-", "&#8209;")}][{a.ref_code}] '
                f"| {a.title_short} "
                f"| {tickmark * n_ticks} "
                f'| {_get_top_subgroup_codes(a.subgroups)} '
                f"| {release_str} "
                f'| {a.date_start.replace("-", "&#8209;")} '
                f"|\n",
            )


def overview(output_dir: Path):
    """Create an analysis/paper overview page for all analyses.

    Parameters:
        output_dir: String for the output directory of the Markdown files.

    """
    logger.info("Generating overview page with tables of analyses and papers.")

    output_file = output_dir / "index.md"
    logger.info(f'Writing output file "{output_file}"')

    with open(output_file, "w", encoding="utf8") as _f:
        _f.write(
            "# Analyses and Papers\n\n\n"
            "The following pages provide an overview of all ongoing analyses and all "
            "submitted/published papers of the top group:\n\n"
            "* [Ongoing Analyses](ongoing.md)\n"
            "* [Submitted/Published Papers](published.md)\n"
            "\n\n"
            "Pages for the individual subgroups:\n\n"
            "* [Cross-section](xs/index.md)\n"
            "    * [Ongoing Analyses](xs/ongoing.md)\n"
            "    * [Submitted/Published Papers](xs/published.md)\n"
            "* [Properties & Mass](pm/index.md)\n"
            "    * [Ongoing Analyses](pm/ongoing.md)\n"
            "    * [Submitted/Published Papers](pm/published.md)\n"
            "* [Top Quarks + X](topx/index.md)\n"
            "    * [Ongoing Analyses](topx/ongoing.md)\n"
            "    * [Submitted/Published Papers](topx/published.md)\n"
            "\n",
        )

    logger.info("Finished generating overview page.")
