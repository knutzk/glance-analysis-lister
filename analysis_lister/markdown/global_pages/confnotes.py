"""Produce Markdown pages for conference notes of the ATLAS top WG.


"""

import logging
from pathlib import Path
from typing import List

from analysis_lister.glance.confnote import ConfNote
from analysis_lister.glance.subgroups import TopGroups
from .. import utils

logger = logging.getLogger(__name__)


def confnotes(
    confnotes: List[ConfNote],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a Markdown page listing CONF notes.

    Args:
        confnotes: List of all CONF notes.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.
        threshold: Year threshold for confnotes to be included.

    """
    logger.info("Generating confnotes overview.")

    output_file = output_dir / "confnotes.md"
    logger.info(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_intro(_f, confnotes)
        _write_confnote_table(_f, confnotes)


def _write_header(_f, last_modified: str):
    """Write the header for the CONF notes page."""
    _f.write("---\nhide:\n -toc\n---\n\n\n")
    _f.write("# Conference notes\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_intro(_f, confnotes: List[ConfNote]):
    """Write the introductory paragraph for the CONF notes page."""
    _f.write(
        f"The following table lists the {len(confnotes)} CONF notes of the "
        "ATLAS top WG that are still the most recent word on their analysis.\n"
        "Notes that a later publication has superseded, and notes whose "
        "analysis has been closed, are not listed.\n\n"
    )


def _write_confnote_table(_f, confnotes: List[ConfNote]):
    """Write the table of conference notes."""
    logger.info("Writing conference note table.")

    _f.write("\n\n")
    _f.write("| Identifier | Analysis | Title | Subgroup | Date |\n")
    _f.write("| --- | --- | --- | --- | --- |\n")

    for cn in confnotes:
        logger.debug(f"Adding conference note {cn.final_ref_code} to table.")
        _f.write(
            f"| [{utils.format_note_id(cn)}]({cn.final_url}) "
            f"| {cn.ref_code.replace('-', '&#8209;')} "
            f"| {cn.title_short.replace('|', '/')} "
            f"| {_format_subgroups(cn.subgroups)} "
            f"| {cn.date_signoff.replace('-', '&#8209;')} |\n"
        )


def _format_subgroups(grps: List[str]) -> str:
    """Return a comma-separated string of top subgroup codes."""
    codes = [g.code for g in TopGroups if g.id in grps]
    return ", ".join(codes) if codes else "None"
