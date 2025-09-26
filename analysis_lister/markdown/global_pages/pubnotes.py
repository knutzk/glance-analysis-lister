"""Produce Markdown pages for PUB notes of the ATLAS top WG.


"""

import logging
from pathlib import Path
from typing import List

from analysis_lister.glance.pubnote import PubNote
from analysis_lister.glance.subgroups import TopGroups
from .. import utils

logger = logging.getLogger(__name__)


def pubnotes(
    pubnotes: List[PubNote],
    output_dir: Path,
    last_modified: str,
    threshold: str = "2020",
):
    """Create a Markdown page listing PUB notes.

    Args:
        pubnotes: List of all PUB notes.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.
        threshold: Year threshold for PUB notes to be included.

    """
    logger.info("Generating PUB notes overview.")

    output_file = output_dir / "pubnotes.md"
    logger.info(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_pubnote_table(_f, pubnotes)


def _write_header(_f, last_modified: str):
    """Write the header for the PUB notes page."""
    _f.write("---\nhide:\n -toc\n---\n\n\n")
    _f.write("# PUB notes\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_pubnote_table(_f, pubnotes: List[PubNote]):
    """Write the table of PUB notes."""
    logger.info("Writing PUB note table.")

    _f.write("\n\n")
    _f.write("| Identifier | Title | Subgroup | Date |\n")
    _f.write("| --- | --- | --- | --- |\n")

    for pn in pubnotes:
        logger.debug(f"Adding PUB note {pn.ref_code} to table.")
        _f.write(
            f"| {pn.ref_code.replace('-', '&#8209;')} "
            f" ([public page]({pn.final_url})) "
            f"| {pn.title_short.replace('|', '/')} "
            f"| {_format_subgroups(pn.subgroups)} "
            f"| {pn.date_signoff.replace('-', '&#8209;')} |\n"
        )


def _format_subgroups(grps: List[str]) -> str:
    """Return a comma-separated string of top subgroup codes."""
    codes = [g.code for g in TopGroups if g.id in grps]
    return ", ".join(codes) if codes else "None"
