import logging
from pathlib import Path
from analysis_lister.glance.paper import Paper as GlancePaper
from analysis_lister.glance.enums import PublicationState
from ..render.paper import render_paper_block
from ..render import utils

logger = logging.getLogger(__name__)

def published_papers(
    list_of_papers: list[GlancePaper],
    output_dir: Path,
    subgroup_title: str,
    subgroup_id: str,
    last_modified: str,
    threshold: str = "2020",
):
    """Create an overview page with publications for one subgroup."""
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
        _f.write("## Submitted papers\n\n")
        for p in subgroup_papers:
            if p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL:
                logger.debug(f"Writing paper block for {p.ref_code}.")
                _f.write(render_paper_block(p))

        _f.write("## Published papers\n\n")
        for p in subgroup_papers:
            if p.pub_state == PublicationState.PUBLISHED:
                logger.debug(f"Writing paper block for {p.ref_code}.")
                _f.write(render_paper_block(p))

    logger.info(f"Finished writing published papers page for subgroup '{subgroup_id}'.")
