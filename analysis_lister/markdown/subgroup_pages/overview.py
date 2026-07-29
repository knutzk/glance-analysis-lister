"""Produce Markdown page with all analyses and papers for a subgroup.


"""

import logging
from pathlib import Path
from typing import List

from analysis_lister.glance.analysis import Analysis as GlanceAnalysis
from analysis_lister.glance.enums import PublicationState
from analysis_lister.glance.paper import Paper as GlancePaper

from .. import utils

logger = logging.getLogger(__name__)


def overview(
    list_of_papers: list[GlancePaper],
    list_of_analyses: list[GlanceAnalysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an analysis/paper overview page for one subgroup.

    Args:
        list_of_papers: List of all papers.
        list_of_analyses: List of all analyses.
        output_dir: Directory to write the output file.
        subgroup_title: Title of the subgroup.
        subgroup_id: ID of the subgroup.
        last_modified: Last modified date for the page.
        threshold: Year threshold for papers to be included.

    """
    subgroup_papers = [p for p in list_of_papers if subgroup_id in p.subgroups]
    subgroup_analyses = [a for a in list_of_analyses if subgroup_id in a.subgroups]

    logger.info(f'Writing output file "{output_dir}/index.md"')
    with open(output_dir / "index.md", "w", encoding="utf8") as _f:
        _f.write(utils.HIDE_TOC)
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
        _f.write(render_analysis_table(subgroup_analyses, subgroup_id))
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
        _f.write(render_paper_table(subgroup_papers, subgroup_id))

    logger.info(f"Finished writing overview page for subgroup '{subgroup_id}'.")


def render_analysis_table(analyses: List[GlanceAnalysis], subgroup_id: str) -> str:
    """Render a Markdown table with analyses.

    Args:
        analyses: List of analyses.
        subgroup_id: ID of the subgroup, used to link to the analysis
            blocks on the pages of this very subgroup.

    Returns:
        str: Markdown table with analyses.

    """
    lines = [
        "| Identifier | Title | EB PA A | Rel. | Start |",
        "| --- | --- | --- | --- | --- |",
    ]

    tickmark = "&#10003;&nbsp;"
    state_to_n_ticks = {
        PublicationState.PHASE1_OR_2: 3,
        PublicationState.PAST_PHASE0: 3,
        PublicationState.PREAPPROVED: 2,
        PublicationState.ONGOING_WITH_EB: 1,
    }

    for a in analyses:
        title = a.title_short.replace("|", "/")
        n_ticks = state_to_n_ticks.get(a.pub_state, 0)

        row = (
            f"| {utils.render_ref_link(a, subgroup_id)} "
            f"| {title} "
            f"| {tickmark * n_ticks} "
            f"| {a.software_release.value} "
            f'| {a.date_start.replace("-", "&#8209;")} |'
        )
        lines.append(row)

    return "\n".join(lines) + "\n"


def render_paper_table(papers: List[GlancePaper], subgroup_id: str) -> str:
    """Render a Markdown table with papers.

    Args:
        papers: List of papers.
        subgroup_id: ID of the subgroup, used to link to the paper blocks
            on the pages of this very subgroup.

    Returns:
        str: Markdown table with papers.

    """
    lines = [
        "| Identifier | Title | Submission | Publication |",
        "| --- | --- | --- | --- |",
    ]

    for p in papers:
        title = p.title_short.replace("|", "/")
        row = (
            f"| {utils.render_ref_link(p, subgroup_id)} "
            f"| {title} "
            f'| {p.date_submission.replace("-", "&#8209;")} '
            f'| {p.date_publication.replace("-", "&#8209;")} |'
        )
        lines.append(row)

    return "\n".join(lines) + "\n"
