# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Provide markdown-formatted information blocks for analyses and papers."""

import logging
from datetime import datetime

from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.subgroups import (
    GroupsById,
    TopGroups,
    canonical_subgroup,
)
from analysis_lister.glance.utils import has_note_number

logger = logging.getLogger(__name__)

# Front matter that keeps the Material theme from rendering a table of
# contents, used by the pages that are one large table and would only get an
# empty one. The value has to be a YAML list, hence the "- ".
HIDE_TOC = "---\nhide:\n  - toc\n---\n\n\n"


def format_date_long(date_str: str) -> str:
    """Convert YYYY-MM-DD to '5 Jan 2025', falling back to the raw string."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d %b %Y")
    except (ValueError, TypeError):
        return date_str


def format_subgroup_codes(subgroups: list[str]) -> str:
    """Return the top WG subgroups of an entry as a table cell.

    Args:
        subgroups: Subgroup ids of an entry, as taken from GLANCE.

    Returns:
        str object with the comma-separated subgroup codes, or "None" if the
        entry belongs to no top WG subgroup.

    """
    codes = [g.code for g in TopGroups if g.id in subgroups]
    return ", ".join(codes) if codes else "None"


def anchor_id(ref_code: str, subgroup_id: str) -> str:
    """Return the anchor of an entry on the page of one subgroup.

    An entry can belong to several subgroups and is then rendered on
    several subgroup pages. Prefixing the anchor with the subgroup code
    keeps the anchors unique across the whole site, which mkdocs-autorefs
    needs in order to resolve reference-style links unambiguously.

    Args:
        ref_code: Reference code of the entry, e.g. "TOPQ-2023-33".
        subgroup_id: GLANCE id of the subgroup whose page is rendered.

    Returns:
        str object with the anchor, e.g. "xs-TOPQ-2023-33".

    """
    group = GroupsById.get(subgroup_id)
    if group is None:
        logger.warning(f'Unknown subgroup "{subgroup_id}", using unprefixed anchor.')
        return ref_code
    return f"{group.code.lower()}-{ref_code}"


def render_ref_link(p: Analysis | Paper, subgroup_id: str = "") -> str:
    """Return the link to the detailed block of an analysis or a paper.

    The link is a reference-style link that mkdocs-autorefs resolves to
    whichever page carries the anchor. Hyphens in the label are replaced
    by non-breaking ones to keep the reference code on a single line.

    Args:
        p: Analysis or Paper instance to link to.
        subgroup_id: GLANCE id of the subgroup page to link to. If empty
            (the default, used by the global pages), the canonical
            subgroup of the entry is used.

    Returns:
        str object with the link, or the plain reference code if the entry
        belongs to no top WG subgroup and hence has no anchor anywhere.

    """
    label = p.ref_code.replace("-", "&#8209;")

    if not subgroup_id:
        group = canonical_subgroup(p.subgroups)
        if group is None:
            logger.warning(
                f"{p.ref_code} belongs to no top WG subgroup, cannot link to it."
            )
            return label
        subgroup_id = group.id

    return f"[{label}][{anchor_id(p.ref_code, subgroup_id)}]"


def format_note_id(note) -> str:
    """Return the number of a CONF/PUB note, ready for a table cell.

    GLANCE pads the column and, as long as a note has no number of its own,
    fills it with a placeholder such as "PUB-TOPQ-2019-24  TEMP ". Such notes
    are not published and hence not listed, so seeing one here is worth a
    warning rather than a silent workaround.

    Args:
        note: ConfNote or PubNote instance to label.

    Returns:
        str object with the note number, hyphens replaced by non-breaking
        ones to keep it on a single line.

    """
    ref = " ".join(note.final_ref_code.split())
    if not has_note_number(note.final_ref_code):
        logger.warning(
            "%s is listed with the temporary note number '%s'.", note.ref_code, ref
        )

    return ref.replace("-", "&#8209;")


def render_glance_links(p: Analysis | Paper, prepend: str = ""):
    """Return the glance link(s) for an analysis or a paper.

    Args:
        p: Analysis or Paper instance for which to provide glance links.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the glance links for an analysis or a paper.

    """
    s = f"{prepend}**Glance:**\n"
    s += f"{prepend}[ANA-{p.ref_code}]({p.glance_url_analysis}) (analysis)"

    # A record only gets a publication of its own once it has left phase 0.
    if "Finished" in p.status and p.glance_url_publ:
        if "confnotes/" in p.glance_url_publ:
            kind = "CONF note"
        elif "pubnotes/" in p.glance_url_publ:
            kind = "PUB note"
        else:
            kind = "paper"
        s += f",\n{prepend}[{p.ref_code}]({p.glance_url_publ}) ({kind})"

    return s + f"\n{prepend}\n"


def render_pub_links(p: Paper, prepend: str = ""):
    """Return the list of publication links for a paper.

    Args:
        p: Paper instance for which to provide the publication links.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the publication links.

    """
    links = []
    if p.inspire_url != "":
        links.append(f"[inspire]({p.inspire_url})")

    for i, doi_url in enumerate(p.doi_urls):
        label = "DOI" if i == 0 else "DOI (erratum/addendum)"
        links.append(f"[{label}]({doi_url})")

    if p.arxiv_url != "":
        links.append(f"[arXiv]({p.arxiv_url})")

    if p.figure_url != "":
        links.append(f"[public page]({p.figure_url})")

    # Joining rather than appending a separator to each link keeps the last
    # one free of a trailing comma, whichever of them a paper happens to have.
    s = f"{prepend}**Publication:**\n"
    s += "".join(f"{prepend}{link}, \n" for link in links[:-1])
    if links:
        s += f"{prepend}{links[-1]}\n"

    return s + f"{prepend}\n"


def render_email_links(p: Analysis | Paper, prepend: str = ""):
    """Return the email links for an analysis or a paper.

    Args:
        p: Analysis or Paper instance for which to provide the email lists.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the email lists.

    """
    # The e-groups of an analysis are named after its full reference code, so
    # the working group code has to be taken from the entry: the top WG lists
    # a good dozen analyses that another group leads (EXOT, STDM, BPHY, ...),
    # and a hard-coded "topq" sends their readers to a list that exists for a
    # different analysis, or for none at all.
    egroup = p.ref_code.lower()
    s = f"{prepend}**Send an email to the:**\n{prepend}\n"
    s += f"{prepend}* Analysis team: "
    s += f"<atlas-{egroup}-analysis-team@cern.ch><br>\n"
    s += f"{prepend}* Editorial board & conveners: "
    s += f"<atlas-{egroup}-edboard-conveners@cern.ch> (†)<br>\n"
    s += f"{prepend}\n"
    if p.editorial_board == "":
        s += f"{prepend}(†) Members: editorial board (once assigned), "
    else:
        s += f"{prepend}(†) Members: editorial board, "

    s += "group conveners, subgroup conveners, PubCom chair\n"
    return s + "\n"


def _update_clock_icon():
    """Print the clock icon with a pencil (modification date).

    Returns: String with a Markdown span that contains the clock icon.

    """
    return (
        '<span class="md-icon" title="Synced with glance">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M21 13.1c-.1 0-.3.1-.4.2l-1 1 2.1 2.1 1-1c.2-.2.2-.6 0-.8l-'
        "1.3-1.3c-.1-.1-.2-.2-.4-.2m-1.9 1.8-6.1 6V23h2.1l6.1-6.1-2.1-2M12.5 "
        "7v5.2l4 2.4-1 1L11 13V7h1.5M11 21.9c-5.1-.5-9-4.8-9-9.9C2 6.5 6.5 2 "
        "12 2c5.3 0 9.6 4.1 10 9.3-.3-.1-.6-.2-1-.2s-.7.1-1 .2C19.6 7.2 16.2 "
        '4 12 4c-4.4 0-8 3.6-8 8 0 4.1 3.1 7.5 7.1 7.9l-.1.2v1.8Z">'
        "</path></svg></span>"
    )


def print_header_timestamp(mtime: str):
    """Return the timestamp that goes into the page headers.

    Returns: The code that creates that footer that goes on all markdown
        pages. This includes a span that shows the page creation date and
        the date of the last sync with the GLANCE database.

    """
    return (
        '<aside class="md-source-file"><span class="md-source-file__fact">'
        f"{_update_clock_icon()}Synced with glance: {mtime}"
        "</span></aside>\n\n"
    )
