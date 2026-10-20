"""Produce Markdown pages for ongoing analyses of a subgroup.


"""

import logging
from pathlib import Path

from analysis_lister.glance.analysis import Analysis as GlanceAnalysis
from analysis_lister.glance.enums import PublicationState
from analysis_lister.lookup_dicts.short_titles import ShortTitles

from .. import utils

logger = logging.getLogger(__name__)


def ongoing_analyses(
    list_of_analyses: list[GlanceAnalysis],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
):
    """Create a page with ongoing analyses for one subgroup.

    Args:
        list_of_analyses: List of all analyses.
        output_dir: Directory to write the output file.
        subgroup_title: Title of the subgroup.
        subgroup_id: ID of the subgroup.
        last_modified: Last modified date for the page.

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
            "without an Editorial Board.\n\n\n"
        )

        _f.write("## Analyses beyond pre-approval\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state in [
                PublicationState.PREAPPROVED,
                PublicationState.PHASE1_OR_2,
            ]:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a, subgroup_id))

        _f.write("## Analyses with EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WITH_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a, subgroup_id))

        _f.write("## Analyses w/o EdBoard\n\n\n")
        for a in subgroup_analyses:
            if a.pub_state == PublicationState.ONGOING_WO_EB:
                logger.debug(f"Writing analysis block for {a.ref_code}.")
                _f.write(render_analysis_block(a, subgroup_id))

    logger.info(f"Finished writing ongoing analyses page for subgroup '{subgroup_id}'.")


def render_analysis_block(
    analysis: GlanceAnalysis,
    subgroup_id: str = "",
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
) -> str:
    """Create a Markdown block for a single analysis.

    Args:
        analysis: The Analysis object.
        subgroup_id: ID of the subgroup whose page is rendered, needed for
            the anchor tag.
        title: Whether to include the short title in the heading.
        attribute_tag: Whether to add an anchor tag for linking.
        heading_level: Heading level (e.g., 3 for ###).

    Returns:
        A Markdown string with all relevant analysis metadata.
    """
    heading = f"{'#' * heading_level} {analysis.ref_code}"
    short_title = ShortTitles.get(analysis.ref_code, analysis.title_short)
    if title:
        heading += f" – {short_title}"
    if attribute_tag:
        heading += f" {{: #{utils.anchor_id(analysis.ref_code, subgroup_id)}}}"

    s = heading + "\n\n"
    s += f'!!! info "{analysis.title_short}"\n\n'
    s += utils.render_glance_links(analysis, prepend="    ")
    s += _involved_subgroups(analysis, prepend="    ")
    s += "    **Supporting documents:**"
    if analysis.supporting_docs:
        s += " " + ", ".join(f"<{x}>" for x in analysis.supporting_docs) + "\n\n"
    else:
        s += " (none)\n\n"
    s += utils.render_email_links(analysis, prepend="    ")

    s += "| Position | Names |\n"
    s += "| --- | --- |\n"
    s += f"| INT note editors | {analysis.int_note_editors} |\n"
    s += f"| Analysis contact(s) | {analysis.contacts} |\n"
    s += f"| Contact editors | {analysis.contact_editors} |\n"
    s += f"| Editorial Board | {analysis.editorial_board} |\n"
    s += "\n"

    s += f"Status: {analysis.phase_state}\n\n"
    s += _render_last_milestone(analysis)
    return s + "\n"


def _render_last_milestone(analysis: GlanceAnalysis) -> str:
    """Return the line naming the review milestone passed most recently.

    The status above it says where in the review an analysis stands, but not
    since when. Every ongoing analysis has at least a phase 0 start date, so
    the line is there even for one that has not moved since.

    """
    milestone = analysis.last_milestone()
    if milestone is None:
        logger.warning(
            "%s carries no milestone date at all, not even a phase 0 start.",
            analysis.ref_code,
        )
        return ""

    label, date = milestone
    return f"Last milestone: {label} on {utils.format_date_long(date)}\n\n"


def _involved_subgroups(analysis: GlanceAnalysis, prepend: str = "") -> str:
    """Return a Markdown list of all involved subgroups."""
    s = f"{prepend}**Involved subgroups:**<br>\n"
    for subgroup in analysis.subgroups:
        s += f"{prepend}* {subgroup}<br>\n"
    return s + f"{prepend}\n"
