# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Shared table rendering for published CONF and PUB notes."""

import logging
from collections.abc import Iterable
from typing import TextIO

from analysis_lister.glance.confnote import ConfNote
from analysis_lister.glance.pubnote import PubNote

from .. import utils

logger = logging.getLogger(__name__)


def write_note_table(stream: TextIO, notes: Iterable[ConfNote | PubNote]) -> None:
    """Write already-selected notes in input order, preserving Markdown escaping."""
    logger.debug("Writing publication note table.")
    stream.write("\n\n")
    stream.write("| Identifier | Analysis | Title | Subgroup | Date |\n")
    stream.write("| --- | --- | --- | --- | --- |\n")

    for note in notes:
        logger.debug("Adding publication note %s to table.", note.final_ref_code)
        stream.write(
            f"| [{utils.format_note_id(note)}]({note.final_url}) "
            f"| {note.ref_code.replace('-', '&#8209;')} "
            f"| {note.title_short.replace('|', '/')} "
            f"| {utils.format_subgroup_codes(note.subgroups)} "
            f"| {note.date_signoff.replace('-', '&#8209;')} |\n"
        )
