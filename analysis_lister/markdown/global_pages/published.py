# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Produce Markdown pages for published papers of the ATLAS top WG."""

import logging
from pathlib import Path

from analysis_lister.glance.enums import PublicationState
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.subgroups import TopGroups

from .. import utils

logger = logging.getLogger(__name__)


def published(
    papers: list[Paper],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a Markdown page listing submitted and published top papers.

    Args:
        papers: List of all papers.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.
        threshold: Year threshold for papers to be included.

    """
    logger.debug("Generating published papers overview.")

    output_file = output_dir / "published.md"
    logger.debug(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_summary(_f, papers, threshold)
        _write_subgroup_counts(_f, papers, threshold)
        _write_table(_f, papers)


def _write_header(_f, last_modified: str):
    """Write the header for the published papers page."""
    _f.write(utils.HIDE_TOC)
    _f.write("# Submitted/published papers\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_summary(_f, papers: list[Paper], threshold: str):
    """Write a summary of the submitted and published papers."""
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


def _write_subgroup_counts(_f, papers: list[Paper], threshold: str):
    """Write the counts of papers per subgroup since a given threshold."""
    logger.debug("Writing subgroup paper counts.")
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


def _write_table(_f, papers: list[Paper]):
    """Write the table of submitted and published papers."""
    logger.debug("Writing paper table.")

    _f.write("| Identifier | Title | Subgroup | Submission | Publication |\n")
    _f.write("| --- | --- | --- | --- | --- |\n")

    for p in papers:
        logger.debug(f"Adding paper {p.ref_code} to table.")
        _f.write(
            f"| {utils.render_ref_link(p)} "
            f"| {p.title_short.replace('|', '/')} "
            f"| {utils.format_subgroup_codes(p.subgroups)} "
            f"| {p.date_submission.replace('-', '&#8209;')} "
            f"| {p.date_publication.replace('-', '&#8209;')} |\n"
        )
