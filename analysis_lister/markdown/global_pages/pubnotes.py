"""Produce Markdown pages for PUB notes of the ATLAS top WG.


"""

import logging
from pathlib import Path

from analysis_lister.glance.pubnote import PubNote

from .. import utils

logger = logging.getLogger(__name__)


def pubnotes(
    pubnotes: list[PubNote],
    output_dir: Path,
    last_modified: str,
):
    """Create a Markdown page listing PUB notes.

    Args:
        pubnotes: List of all PUB notes.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.

    """
    logger.info("Generating PUB notes overview.")

    output_file = output_dir / "pubnotes.md"
    logger.info(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_intro(_f, pubnotes)
        _write_pubnote_table(_f, pubnotes)


def _write_header(_f, last_modified: str):
    """Write the header for the PUB notes page."""
    _f.write(utils.HIDE_TOC)
    _f.write("# PUB notes\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_intro(_f, pubnotes: list[PubNote]):
    """Write the introductory paragraph for the PUB notes page."""
    _f.write(
        f"The following table lists the {len(pubnotes)} PUB notes of the "
        "ATLAS top WG that are still the most recent word on their analysis.\n"
        "Notes that a later publication has superseded, and notes whose "
        "analysis has been closed or never started, are not listed.\n\n"
    )


def _write_pubnote_table(_f, pubnotes: list[PubNote]):
    """Write the table of PUB notes."""
    logger.info("Writing PUB note table.")

    _f.write("\n\n")
    _f.write("| Identifier | Analysis | Title | Subgroup | Date |\n")
    _f.write("| --- | --- | --- | --- | --- |\n")

    for pn in pubnotes:
        logger.debug(f"Adding PUB note {pn.final_ref_code} to table.")
        _f.write(
            f"| [{utils.format_note_id(pn)}]({pn.final_url}) "
            f"| {pn.ref_code.replace('-', '&#8209;')} "
            f"| {pn.title_short.replace('|', '/')} "
            f"| {utils.format_subgroup_codes(pn.subgroups)} "
            f"| {pn.date_signoff.replace('-', '&#8209;')} |\n"
        )
