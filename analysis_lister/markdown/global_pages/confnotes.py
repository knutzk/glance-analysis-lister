# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Produce Markdown pages for conference notes of the ATLAS top WG."""

import logging
from pathlib import Path

from analysis_lister.glance.confnote import ConfNote

from .. import utils
from .note_table import write_note_table

logger = logging.getLogger(__name__)


def confnotes(
    confnotes: list[ConfNote],
    output_dir: Path,
    last_modified: str,
):
    """Create a Markdown page listing CONF notes.

    Args:
        confnotes: List of all CONF notes.
        output_dir: Directory to write the output file.
        last_modified: Last modified date for the page.

    """
    logger.info("Generating confnotes overview.")

    output_file = output_dir / "confnotes.md"
    logger.info(f'Writing output file "{output_file}"')

    with output_file.open("w", encoding="utf8") as _f:
        _write_header(_f, last_modified)
        _write_intro(_f, confnotes)
        write_note_table(_f, confnotes)


def _write_header(_f, last_modified: str):
    """Write the header for the CONF notes page."""
    _f.write(utils.HIDE_TOC)
    _f.write("# Conference notes\n\n")
    _f.write(utils.print_header_timestamp(last_modified))


def _write_intro(_f, confnotes: list[ConfNote]):
    """Write the introductory paragraph for the CONF notes page."""
    _f.write(
        f"The following table lists the {len(confnotes)} CONF notes of the "
        "ATLAS top WG that are still the most recent word on their analysis.\n"
        "Notes that a later publication has superseded, and notes whose "
        "analysis has been closed, are not listed.\n\n"
    )
