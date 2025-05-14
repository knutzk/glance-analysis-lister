import logging

from analysis_lister.glance.paper import Paper
from analysis_lister.lookup_dicts.short_titles import ShortTitles
from . import utils

logger = logging.getLogger(__name__)


def render_paper_block(
    paper: Paper,
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
) -> str:
    """Render a full Markdown block for a paper.

    Args:
        paper: The Paper instance to render.
        title: If True, include a heading with the paper title.
        attribute_tag: If True, attach a Markdown attribute tag for linking.
        heading_level: Heading level for the Markdown title.

    Returns:
        str: Rendered Markdown block.
    """
    s = ""

    if not title:
        s += heading_level * "#" + f" {paper.ref_code}"
    elif paper.ref_code in ShortTitles:
        s += heading_level * "#" + f" {paper.ref_code} – {ShortTitles[paper.ref_code]}"
    else:
        logger.warning(f"No short title found for {paper.ref_code}. Using fallback.")
        s += heading_level * "#" + f" {paper.ref_code} – {paper.title_short}"

    if attribute_tag:
        s += f" {{: #{paper.ref_code}}}"
    s += "\n\n"

    s += f"> [!info] {paper.title_short_public}\n> \n"
    s += utils.render_glance_links(paper, prepend="> ")
    s += utils.render_pub_links(paper, prepend="> ")
    s += utils.render_email_links(paper, prepend="> ")

    s += render_submission_status(paper)
    s += f"**Editorial Board:** {paper.editorial_board}\n\n"
    s += f"**Contact Editors:** {paper.contact_editors}\n\n"

    if paper.date_submission:
        s += "Cite as:\n"
        s += render_citation_block(paper, prepend="> ")

    return s + "\n\n"


def render_submission_status(p: Paper) -> str:
    if p.date_publication:
        return f"**Status:** published since {p.date_publication}\n\n"
    elif p.date_acceptance:
        return f"**Status:** submitted to {p.journal} on {p.date_submission} and accepted on {p.date_acceptance}\n\n"
    elif p.date_submission and p.journal:
        return f"**Status:** submitted to {p.journal} on {p.date_submission}\n\n"
    elif p.date_submission:
        return f"**Status:** submitted to [JOURNAL] on {p.date_submission}\n\n"
    return "**Status:** not submitted\n\n"


def render_citation_block(p: Paper, prepend: str = "") -> str:
    s = f"{prepend}ATLAS Collaboration<br>\n"
    s += f"{prepend}{p.title_final_tex}<br>\n"
    s += f"{prepend}{p.journal_ref}, {p.arxiv_number}<br>\n"
    if p.doi:
        s += f"{prepend}DOI: {p.doi}<br>\n"
    return s + "\n"
