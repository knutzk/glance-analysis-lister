"""Produce Markdown pages for published papers of a subgroup.


"""

import logging
from datetime import datetime
from pathlib import Path
from analysis_lister.glance.paper import Paper as GlancePaper
from analysis_lister.glance.enums import PublicationState
from analysis_lister.lookup_dicts.short_titles import ShortTitles
from .. import utils

logger = logging.getLogger(__name__)


def published_papers(
    list_of_papers: list[GlancePaper],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an overview page with publications for one subgroup.

    Args:
        list_of_papers: List of all papers.
        output_dir: Directory to write the output file.
        subgroup_title: Title of the subgroup.
        subgroup_id: ID of the subgroup.
        last_modified: Last modified date for the page.
        threshold: Year threshold for papers to be included.

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
            f"that were published in {threshold} or later.\n\n\n"
        )
        submitted = sorted(
            (p for p in subgroup_papers if p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL),
            key=lambda p: p.date_submission or "",
            reverse=True,
        )
        published = sorted(
            (p for p in subgroup_papers if p.pub_state == PublicationState.PUBLISHED),
            key=lambda p: p.date_publication or "",
            reverse=True,
        )

        _f.write("## Submitted papers\n\n")
        for p in submitted:
            logger.debug(f"Writing paper block for {p.ref_code}.")
            _f.write(render_paper_block(p, subgroup_id))

        _f.write("## Published papers\n\n")
        for p in published:
            logger.debug(f"Writing paper block for {p.ref_code}.")
            _f.write(render_paper_block(p, subgroup_id))

    logger.info(f"Finished writing published papers page for subgroup '{subgroup_id}'.")


def render_paper_block(
    paper: GlancePaper,
    subgroup_id: str = "",
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
) -> str:
    """Render a full Markdown block for a paper.

    Args:
        paper: The Paper instance to render.
        subgroup_id: ID of the subgroup whose page is rendered, needed for
            the anchor tag.
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
        s += f" {{: #{utils.anchor_id(paper.ref_code, subgroup_id)}}}"
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


def _fmt(date_str: str) -> str:
    """Convert YYYY-MM-DD to '5 Jan 2025', falling back to the raw string."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d %b %Y")
    except (ValueError, TypeError):
        return date_str


def render_submission_status(p: GlancePaper) -> str:
    """Render the submission status of a paper."""
    if p.date_publication:
        return f"**Status:** published since {_fmt(p.date_publication)}\n\n"
    elif p.date_acceptance:
        return f"**Status:** submitted to {p.journal} on {_fmt(p.date_submission)} and accepted on {_fmt(p.date_acceptance)}\n\n"
    elif p.date_submission and p.journal:
        return f"**Status:** submitted to {p.journal} on {_fmt(p.date_submission)}\n\n"
    elif p.date_submission:
        return f"**Status:** submitted to [JOURNAL] on {_fmt(p.date_submission)}\n\n"
    return "**Status:** not submitted\n\n"


def render_citation_block(p: GlancePaper, prepend: str = "") -> str:
    """Render the citation block for a paper."""
    s = f"{prepend}ATLAS Collaboration<br>\n"
    s += f"{prepend}{p.title_final_tex}<br>\n"
    s += f"{prepend}{p.journal_ref}, {p.arxiv_number}<br>\n"
    if p.dois:
        s += f"{prepend}DOI: {p.dois[0]}<br>\n"

    # Errata and addenda are cited below the paper, each on its own line.
    for ref, doi in zip(p.journal_ref_corrections, p.dois[1:]):
        cite = ", ".join(x for x in (ref, f"DOI: {doi}") if x)
        s += f"{prepend}[{cite}]<br>\n"

    return s + "\n"
