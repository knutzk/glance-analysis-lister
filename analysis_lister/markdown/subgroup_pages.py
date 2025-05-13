"""Create pages in Markdown specific to subgroups.


"""

from . import utils
from pathlib import Path
from analysis_lister.glance import analysis, paper
from analysis_lister.glance.enums import PublicationState
import logging

# Set up logging
logger = logging.getLogger(__name__)


def ongoing_analyses(
    list_of_analyses: list[analysis.Analysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
):
    """Create a page with ongoing analyses for one subgroup.

    Takes a list of analyses and produces a Markdown page with subsections for
    each analysis. The analyses are filtered based on the 'subgroup_id' string
    being part of the 'Subgroups' field in GLANCE. The analyses are listed
    in separate subsectinos depending on their stage in the approval process.

    Parameters:
        list_of_analyses: A list of analysis objects considered for the overview
            tables.
        output_dir: String for the output directory of the Markdown files.
        subgroup_title: String with the name of the subgroup (used for
            Markdown headings).
        subgroup_id: String with the subgroup ID that is stored in GLANCE.

    """
    subgroup_analyses = [a for a in list_of_analyses if subgroup_id in a.subgroups]

    logger.info(f'Writing output file "{output_dir}/ongoing.md"')
    with open(output_dir / "ongoing.md", "w", encoding="utf8") as _f:
        _f.write(f"# {subgroup_title} – Ongoing Analyses\n\n\n")
        _f.write(utils.print_header_timestamp(last_modified))

        logger.info(
            f'Found {len(subgroup_analyses)} ongoing analyses for subgroup "{subgroup_id}".'
        )
        _f.write(
            f"There are currently {len(subgroup_analyses)} ongoing analyses "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup.\n"
            "The following lists separate those analyses beyond the subgroup "
            "pre-approval, those with an Editorial Board assigned, and those "
            "without an Editorial Board.\n"
            "\n\n",
        )
        _f.write("## Analyses beyond pre-approval\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state in [
                PublicationState.PREAPPROVED,
                PublicationState.PHASE1_OR_2,
            ]:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(utils.analysis_block(a))

        _f.write("## Analyses with EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WITH_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(utils.analysis_block(a))

        _f.write("## Analyses w/o EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WO_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(utils.analysis_block(a))

    logger.info(f"Finished writing ongoing analyses page for subgroup '{subgroup_id}'.")


def overview(
    list_of_papers: list[paper.Paper],
    list_of_analyses: list[analysis.Analysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an analysis/paper overview page for one subgroup.

    Takes a list of papers and a list of analyses, and produces a Markdown
    page with overview tables of both. The papers and analyses are filtered
    based on the 'subgroup_id' string being part of the 'Subgroups' field in
    GLANCE. Only papers published in 'threshold' or later will be listed.

    Parameters:
        list_of_papers: List of papers considered for the overview tables.
        list_of_analyses: List of analyses considered for the overview tables.
        output_dir: String for the output directory of the Markdown files.
        subgroup_title: String with the name of the subgroup (used to set up
            headings in Markdown).
        subgroup_id: String with the subgroup ID that is stored in GLANCE.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    subgroup_papers = [p for p in list_of_papers if subgroup_id in p.subgroups]
    subgroup_analyses = [a for a in list_of_analyses if subgroup_id in a.subgroups]

    logger.info(f'Writing output file "{output_dir}/index.md"')
    with open(output_dir / "index.md", "w", encoding="utf8") as _f:
        _f.write("---\nhide:\n -toc\n---\n\n\n")
        _f.write(f"# {subgroup_title} – Analyses and Papers\n\n\n")

        _f.write(utils.print_header_timestamp(last_modified))

        logger.info(
            f'Found {len(subgroup_analyses)} ongoing analyses for subgroup "{subgroup_id}".'
        )
        _f.write("## Ongoing Analyses\n\n")
        _f.write(
            f"There are currently {len(subgroup_analyses)} ongoing analyses "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup.\n\n"
            '- The "**EB PA A**" column indicates the review status of the analyses:\n'
            "    - One tick mark = EdBoard is assigned (EB),\n"
            "    - two tick marks = analysis is pre-approved (PA),\n"
            "    - three tick marks = analysis is group-approved (A).\n"
            '- "**Rel.**" shows the software release the analysis uses – it is based '
            "on the keywords assigned to the analysis on GLANCE.\n"
            '- "**Start**" is the date the analysis started.\n\n'
        )
        _f.write("| Identifier | Title | EB PA A | Rel. | Start |\n")
        _f.write("| --- | --- | --- | --- | --- |\n")
        for a in subgroup_analyses:
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

            _f.write(
                f'| [{a.ref_code.replace("-", "&#8209;")}][{a.ref_code}] '
                f'| {a.title_short.replace("|", "/")} '
                f"| {tickmark * n_ticks} "
                f"| {release_str} "
                f'| {a.date_start.replace("-", "&#8209;")} '
                f"|\n",
            )

        _f.write("\n\n\n")

        logger.info(
            f"Found {len(subgroup_papers)} submitted and published papers for "
            f'subgroup "{subgroup_id}".'
        )

        _f.write("## Submitted/Published Papers\n\n")
        _f.write(
            f"There are {len(subgroup_papers)} submitted and published papers "
            f'for which "{subgroup_id}" is listed as the leading or an '
            "additional subgroup (only considering papers published in "
            f"{threshold} or after).\n\n"
        )
        _f.write("| Identifier | Title | Submission | Publication |\n")
        _f.write("| --- | --- | --- | --- |\n")
        for p in subgroup_papers:
            logger.debug(f"Writing table row for paper {p.ref_code}.")
            _f.write(
                f'| [{p.ref_code.replace("-", "&#8209;")}][{p.ref_code}] '
                f'| {p.title_short.replace("|", "/")} '
                f'| {p.date_submission.replace("-", "&#8209;")} '
                f'| {p.date_publication.replace("-", "&#8209;")} '
                f"|\n",
            )

    logger.info(f"Finished writing overview page for subgroup '{subgroup_id}'.")


def published_papers(
    list_of_papers: list[paper.Paper],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an overview page with publications for one subgroup.

    Takes a list of papers and produces a Markdown page with subsections for
    each publication. The papers are filtered based on the 'subgroup_id' string
    being part of the 'Subgroups' field in GLANCE. Only papers submitted or
    published in 'threshold' or later will be listed.

    Parameters:
        list_of_papers: A list of paper objects considered for the overview
            tables.
        output_dir: String for the output directory of the Markdown files.
        subgroup_title: String with the name of the subgroup (used for
            Markdown headings).
        subgroup_id: String with the subgroup ID that is stored in GLANCE.
        threshold: Threshold in the form of a date that is used to set a limit
            on the number of listed publications (only newer than 'threshold').

    """
    subgroup_papers = [p for p in list_of_papers if subgroup_id in p.subgroups]
    n_submitted = sum(
        p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL for p in subgroup_papers
    )
    n_published = sum(
        p.pub_state == PublicationState.PUBLISHED for p in subgroup_papers
    )

    logger.info(f'Writing output file "{output_dir}/published.md"')
    with open(output_dir / "published.md", "w", encoding="utf8") as _f:
        _f.write(f"# {subgroup_title} – Submitted/Published Papers\n\n\n")

        _f.write(utils.print_header_timestamp(last_modified))

        logger.debug(
            f'Found {n_submitted} submitted and {n_published} published papers for subgroup "{subgroup_id}".'
        )
        _f.write(
            f"There are currently {n_submitted} submitted papers for which "
            f'"{subgroup_id}" is listed as the leading or an additional '
            "subgroup.\n"
            f"In addition, there are {n_published} papers of this subgroup "
            f"that were published in {threshold} or later.\n"
            "\n\n",
        )
        _f.write("## Submitted papers\n\n")
        for p in subgroup_papers:
            if p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL:
                logger.debug(f"Writing paper block for {p.ref_code}.")
                _f.write(utils.paper_block(p))

        _f.write("## Published papers\n\n")
        for p in subgroup_papers:
            if p.pub_state == PublicationState.PUBLISHED:
                logger.debug(f"Writing paper block for {p.ref_code}.")
                _f.write(utils.paper_block(p))

    logger.info(f"Finished writing published papers page for subgroup '{subgroup_id}'.")
