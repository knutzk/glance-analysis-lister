"""Provide markdown-formatted information blocks for analyses and papers.


"""

import logging
from typing import Union

from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.subgroups import GroupsById, canonical_subgroup

logger = logging.getLogger(__name__)


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


def render_ref_link(p: Union[Analysis, Paper], subgroup_id: str = "") -> str:
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


def render_glance_links(p: Union[Analysis, Paper], prepend: str = ""):
    """Return the glance link(s) for an analysis or a paper.

    Parameters:
        p: Analysis or Paper instance for which to provide glance links.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the glance links for an analysis or a paper.

    """
    s = f"{prepend}**Glance:**\n"
    s += f"{prepend}[ANA-{p.ref_code}]({p.glance_url_analysis}) (analysis)\n"
    # A record only gets a publication of its own once it has left phase 0.
    if "Finished" not in p.status:
        return s + f"{prepend}\n"

    if p.glance_url_publ and "confnotes/" in p.glance_url_publ:
        s += f"{prepend}, [{p.ref_code}]({p.glance_url_publ}) (CONF note)\n"
    elif p.glance_url_publ and "pubnotes/" in p.glance_url_publ:
        s += f"{prepend}, [{p.ref_code}]({p.glance_url_publ}) (PUB note)\n"
    elif p.glance_url_publ:
        s += f"{prepend}, [{p.ref_code}]({p.glance_url_publ}) (paper)\n"
    return s + f"{prepend}\n"


def render_pub_links(p: Paper, prepend: str = ""):
    """Return the list of publication links for a paper.

    Parameters:
        p: Paper instance for which to provide the publication links.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the publication links.

    """
    s = f"{prepend}**Publication:**\n"
    if p.inspire_url != "":
        s += f"{prepend}[inspire]({p.inspire_url}), \n"

    for i, doi_url in enumerate(p.doi_urls):
        label = "DOI" if i == 0 else "DOI (erratum/addendum)"
        s += f"{prepend}[{label}]({doi_url}), \n"

    if p.arxiv_url != "":
        s += f"{prepend}[arXiv]({p.arxiv_url}), \n"

    if p.figure_url != "":
        s += f"{prepend}[public page]({p.figure_url})\n"

    return s + f"{prepend}\n"


def render_email_links(p: Union[Analysis, Paper], prepend: str = ""):
    """Return the email links for an analysis or a paper.

    Parameters:
        p: Analysis or Paper instnace for which to provide the email lists.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the email lists.

    """
    s = f"{prepend}**Send an email to the:**\n{prepend}\n"
    s += f"{prepend}* Analysis team: "
    s += f"<atlas-topq-{p.ref_code[5:]}-analysis-team@cern.ch><br>\n"
    s += f"{prepend}* Editorial board & conveners: "
    s += f"<atlas-topq-{p.ref_code[5:]}-edboard-conveners@cern.ch> (†)<br>\n"
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
