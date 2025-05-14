import logging

from analysis_lister.glance.analysis import Analysis
from analysis_lister.lookup_dicts.short_titles import ShortTitles

from . import utils

logger = logging.getLogger(__name__)


def render_analysis_block(
    analysis: Analysis,
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
) -> str:
    """Create a Markdown block for a single analysis.

    Args:
        analysis: The Analysis object.
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
        heading += f" {{: #{analysis.ref_code}}}"

    s = heading + "\n\n"
    s += f"> [!info] {analysis.title_short}\n> \n"
    s += utils.render_glance_links(analysis, prepend="> ")
    s += _involved_subgroups(analysis, prepend="> ")
    s += "> **Supporting documents:**"
    if analysis.supporting_docs:
        s += " " + ", ".join(f"<{x}>" for x in analysis.supporting_docs) + "\n> \n"
    else:
        s += " (none)\n> \n"
    s += utils.render_email_links(analysis, prepend="> ")

    s += "| Position | Names |\n"
    s += "| --- | --- |\n"
    s += f"| INT note editors | {analysis.int_note_editors} |\n"
    s += f"| Analysis contact(s) | {analysis.contacts} |\n"
    s += f"| Contact editors | {analysis.contact_editors} |\n"
    s += f"| Editorial Board | {analysis.editorial_board} |\n"
    s += "\n"

    s += f"Status: {analysis.phase_state}\n\n\n"
    return s


def _involved_subgroups(analysis: Analysis, prepend: str = "") -> str:
    """Return a Markdown list of all involved subgroups."""
    s = f"{prepend}**Involved subgroups:**<br>\n"
    for subgroup in analysis.subgroups:
        s += f"{prepend}* {subgroup}<br>\n"
    return s + f"{prepend}\n"
