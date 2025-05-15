import logging
from pathlib import Path
from typing import List

from analysis_lister.glance.enums import PublicationState
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.subgroups import TopGroups
from .. import utils

logger = logging.getLogger(__name__)


def published(
    papers: List[Paper],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a Markdown page listing submitted and published top papers."""
    logger.info("Generating published papers overview.")

    output_file = output_dir / "published.md"
    logger.info(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_summary(_f, papers, threshold)
        _write_subgroup_counts(_f, papers, threshold)
        _write_table(_f, papers)


def _write_header(_f, last_modified: str):
    _f.write("---\nhide:\n -toc\n---\n\n\n")
    _f.write("# Submitted/published papers\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_summary(_f, papers: List[Paper], threshold: str):
    n_submitted = sum(
        p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL for p in papers
    )
    n_published = sum(p.pub_state == PublicationState.PUBLISHED for p in papers)

    logger.debug(f"{n_submitted} submitted, {n_published} published papers found.")

    twiki_link = "https://twiki.cern.ch/twiki/bin/view/AtlasPublic/TopPublicResults"
    _f.write(
        f"There are currently {n_submitted} submitted papers for which one or more of the "
        "ATLAS top WG subgroups is listed as the leading or an additional subgroup.\n"
        f"In addition, {n_published} papers have been published since {threshold}.\n\n"
        f"These and older publications are also listed on the "
        f"[TopPublicResults twiki page]({twiki_link}).\n\n"
    )


def _write_subgroup_counts(_f, papers: List[Paper], threshold: str):
    logger.info("Writing subgroup paper counts.")
    _f.write(f'!!! info "Counts per subgroup (since {threshold})"\n\n')

    for g in TopGroups:
        total = sum(g.id in p.subgroups for p in papers)
        published = sum(
            g.id in p.subgroups and p.pub_state == PublicationState.PUBLISHED
            for p in papers
        )
        submitted = sum(
            g.id in p.subgroups and p.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
            for p in papers
        )
        _f.write(f"    * {g.title}: {total} (published: {published}, ")
        _f.write(f"submitted: {submitted})\n")

    _f.write("\n\n")


def _write_table(_f, papers: List[Paper]):
    logger.info("Writing paper table.")

    _f.write("| Identifier | Title | Subgroup | Submission | Publication |\n")
    _f.write("| --- | --- | --- | --- | --- |\n")

    for p in papers:
        logger.debug(f"Adding paper {p.ref_code} to table.")
        _f.write(
            f"| [{p.ref_code.replace('-', '&#8209;')}][{p.ref_code}] "
            f"| {p.title_short.replace('|', '/')} "
            f"| {_format_subgroups(p.subgroups)} "
            f"| {p.date_submission.replace('-', '&#8209;')} "
            f"| {p.date_publication.replace('-', '&#8209;')} |\n"
        )


def _format_subgroups(grps: List[str]) -> str:
    """Return a comma-separated string of top subgroup codes."""
    codes = [g.code for g in TopGroups if g.id in grps]
    return ", ".join(codes) if codes else "None"
