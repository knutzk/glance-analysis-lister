# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Module providing utility functions to handle analysis/paper GLANCE entries."""

import logging
import re

from attrs import fields as attrs_fields

logger = logging.getLogger(__name__)


def format_contacts(contacts: str, end_dates: str) -> str:
    """Return the current analysis contacts of an analysis.

    Both GLANCE columns are comma-separated lists that have to be read in
    parallel, so a contact whose name contains a comma throws them out of
    step. Zipping them would then silently drop the tail of the longer list,
    which loses current contacts; listing everybody instead keeps the page
    usable and leaves the warning to say why it may show a past contact.

    """
    contacts = contacts.split(", ")
    end_dates = end_dates.split(", ")
    if len(contacts) != len(end_dates):
        logger.warning(
            "Cannot resolve analysis contacts, %d names against %d end dates: "
            "%s. Listing all of them.",
            len(contacts),
            len(end_dates),
            ", ".join(contacts),
        )
        return ", ".join(contacts)

    contacts = [
        c for c, d in zip(contacts, end_dates, strict=True) if d == "No end date"
    ]
    return ", ".join(contacts)


def format_editorial_board(ed_board: str, chairs: str) -> str:
    """Return the editorial board of an analysis, with chairs highlighted."""
    if ed_board == "":
        return ""

    ed_board = [x.strip() for x in ed_board.split(",")]
    chairs = [x.strip() for x in chairs.split(",")]
    ed_board = [f"**{x}** (chair)" if x in chairs else x for x in ed_board]
    return ", ".join(ed_board)


def has_note_number(final_ref_code: str) -> bool:
    """Return whether a CONF/PUB note has a number of its own yet.

    Until a note is assigned one, GLANCE fills its `Reference Code` column
    with a padded placeholder built from the analysis code, such as
    "PUB-TOPQ-2019-24  TEMP ".

    Args:
        final_ref_code: The `Reference Code` of a note, as taken from GLANCE.

    Returns:
        True if the column holds a real note number.

    """
    return bool(final_ref_code.strip()) and "TEMP" not in final_ref_code


def format_ref_code(ref_code: str) -> str:
    """Return the reference code of an analysis/paper."""
    if ref_code.startswith("ANA-"):
        ref_code = ref_code[4:]

    return ref_code


def format_date(date_str: str) -> str:
    """Return the date string, truncated after YYYY-MM-DD."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
    return match.group(1) if match else date_str


# A subgroup as listed by GLANCE, e.g. "TOPQ - Cross-section": a working
# group code, a dash, and the name of the subgroup.
_SUBGROUP_SEPARATOR = re.compile(r",(?=[A-Z][A-Z0-9]{1,5} - )")


def format_subgroups(subgroups: str) -> list[str]:
    """Return the list of subgroups of an analysis or a paper.

    GLANCE joins the subgroups with a bare comma and does not escape the
    commas inside their names, so "STDM - W,Z Physics,TOPQ - Cross-section"
    is ambiguous. Splitting only before a working group code keeps such
    names intact.

    Args:
        subgroups: Comma-separated subgroups, as taken from GLANCE.

    Returns:
        The individual subgroups; a list with one empty string if the
        input is empty, matching the behaviour of str.split().

    """
    return _SUBGROUP_SEPARATOR.split(subgroups)


def format_supporting_docs(supporting_docs: str) -> list[str]:
    """Return the supporting documents of an entry.

    Args:
        supporting_docs: Comma-separated documents, as taken from GLANCE.

    Returns:
        The individual documents, empty if the entry has none.

    """
    return supporting_docs.split(",") if supporting_docs else []


def format_url_inspire(urls: str) -> str:
    """Return the Inspire HEP URL of a paper."""
    urls = ["http" + x.strip() for x in urls.split("http")[1:]]
    urls = list(filter(lambda a: "inspirehep.net" in a, urls))
    return urls[0] if urls else ""


def get_init_fields(source_obj, target_cls):
    """Extract init=True fields from source_obj for target_cls."""
    target_init_fields = {f.name for f in attrs_fields(target_cls) if f.init}
    return {
        name: getattr(source_obj, name)
        for name in target_init_fields
        if hasattr(source_obj, name)
    }


def glance_analysis_url(ref_code: str) -> str:
    """Return the GLANCE URL of an analysis."""
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/analyses/details.php?"
        f"ref_code=ANA-{ref_code}"
    )


def glance_confnote_url(ref_code: str) -> str:
    """Return the GLANCE URL of a CONF note."""
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/confnotes/details.php?"
        f"ref_code=CONF-{ref_code}"
    )


def glance_paper_url(ref_code: str) -> str:
    """Return the GLANCE URL of a paper."""
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/papers/details.php?"
        f"ref_code={ref_code}"
    )


def glance_pubnote_url(ref_code: str) -> str:
    """Return the GLANCE URL of a PUB note."""
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/pubnotes/details.php?"
        f"ref_code=PUB-{ref_code}"
    )


def clean_titles(*titles: str) -> list[str]:
    """Clean the titles of an analysis/publication (replacing pipe chars)."""
    return [t.replace("|", "/") for t in titles]
