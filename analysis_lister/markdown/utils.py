"""Provide markdown-formatted information blocks for analyses and papers.


"""

import git
import os
from datetime import datetime
from typing import List, Union
from zoneinfo import ZoneInfo

from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.paper import Paper
from analysis_lister.lookup_dicts.short_titles import ShortTitles


def analysis_block(
    _ana: Analysis,
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
):
    """Create an information block for an analysis.

    Uses a glance.analysis.Analysis class instance and returns all relevant
    information for that instance, including links to the glance entries, links
    to the supporting documents, the names of INT note editors, analysis
    contacts, contact editors, and EdBoard members (if assigned), as well as
    the relevant email lists.

    Parameters:
        _ana: glance.analysis.Analysis instance to provide information for.
        title: Boolean whether the heading should include the analysis title.
        attribute_tag (bool): Boolean whether to include an attribute tag in heading.
        heading_level (int): The level of the heading to use for the analysis block.

    Returns:
        String containing information about the analysis instance.

    """
    s = ""
    if not title:
        s += heading_level * "#" + f" {_ana.ref_code}"
    elif _ana.ref_code in ShortTitles:
        s += heading_level * "#" + f" {_ana.ref_code} – {ShortTitles[_ana.ref_code]}"
    else:
        s += heading_level * "#" + f" {_ana.ref_code} – {_ana.title_short}"

    if attribute_tag:
        s += f" {{: #{_ana.ref_code}}}"
    s += "\n\n"

    def format_docs(_list):
        """Convert supporting documents into linked URLs.

        Returns:
            String with comma-separated list of supporting document URLs.

        """
        return ", ".join(f"<{x}>" for x in _list)

    s += f"> [!info] {_ana.title_short}\n> \n"
    s += _glance_links(_ana, prepend="> ")
    s += "> **Supporting documents:**"
    if _ana.supporting_docs != []:
        s += f" {format_docs(_ana.supporting_docs)}\n> \n"
    else:
        s += " (none)\n\n"

    s += _email_links(_ana, prepend="> ")

    s += "| Position | Names |\n"
    s += "| --- | --- |\n"
    s += f"| INT note editors | {_ana.int_note_editors} |\n"
    s += f"| Analysis contact(s) | {_ana.contacts} |\n"
    s += f"| Contact editors | {_ana.contact_editors} |\n"
    s += f"| Editorial Board | {_ana.editorial_board} |\n"
    s += "\n"

    s += f"Status: {_ana.phase_state}\n"

    return s + "\n\n"


def _glance_links(p: Union[Analysis, Paper], prepend: str = ""):
    """Return the glance link(s) for an analysis or a paper.

    Parameters:
        p: Analysis or Paper instance for which to provide glance links.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the glance links for an analysis or a paper.

    """
    s = f"{prepend}**Glance:**\n"
    s += f"{prepend}[ANA-{p.ref_code}]({p.glance_url_analysis}) (analysis)\n"
    if isinstance(p, Analysis) and not ("Phase 0" and "Finished" in p.status):
        return s + f"{prepend}\n"

    s += f"{prepend}, [{p.ref_code}]({p.glance_url_paper}) (paper)\n"
    return s + f"{prepend}\n"


def _pub_links(p: Paper, prepend: str = ""):
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

    if p.doi_url != "":
        s += f"{prepend}[DOI]({p.doi_url}), \n"

    if p.arxiv_url != "":
        s += f"{prepend}[arXiv]({p.arxiv_url}), \n"

    if p.figure_url != "":
        s += f"{prepend}[public page]({p.figure_url})\n"

    return s + f"{prepend}\n"


def _email_links(p: Union[Analysis, Paper], prepend: str = ""):
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


def _submission_status(p: Paper):
    """Return the submission status of a paper.

    Parameters:
        p: Paper instnace for which to provide the submission status.

    Returns:
        str object with the submission status.

    """
    s = "**Status:** "
    if p.date_publication != "":
        s += f"published since {p.date_publication}\n"
    elif p.date_acceptance != "":
        s += f"submitted to {p.journal} on {p.date_submission} "
        s += f"and accepted on {p.date_acceptance}\n"
    elif p.date_submission != "" and p.journal != "":
        s += f"submitted to {p.journal} on {p.date_submission}\n"
    elif p.date_submission != "":
        s += f"submitted to [JOURNAL] on {p.date_submission}\n"
    else:
        s += "not submitted\n"

    return s + "\n"


def _citation_block(p: Paper, prepend: str = ""):
    """Create the citation block for a paper.

    Parameters:
        p: Paper instnace for which to provide the citation block.
        prepend: str to prepend to the returned string (for formatting).

    Returns:
        str object with the citation block.

    """
    s = f"{prepend}ATLAS Collaboration<br>\n"
    s += f"{prepend}{p.title_final_tex}<br>\n"
    s += f"{prepend}{p.journal_ref}, {p.arxiv_number}<br>\n"
    if p.doi != "":
        s += f"{prepend}DOI: {p.doi}<br>\n"

    return s + "\n"


def paper_block(
    _paper: Paper,
    title: bool = True,
    attribute_tag: bool = True,
    heading_level: int = 3,
):
    """Create an information block for a paper.

    Uses a glance.paper.Paper class instance and returns all relevant
    information for that instance, including links to the glance entries, links
    to the publication (DOI, arXiv etc.), email lists and a suggestion how the
    publication should be cited.

    Parameters:
        _paper: glance.paper.Paper instance to provide information for.
        title: Boolean whether the heading should include the analysis title.
        attribute_tag (bool): Boolean whether to include an attribute tag in heading.
        heading_level (int): The level of the heading to use for the analysis block.

    Returns:
        String containing information about the analysis instance.

    """
    s = ""
    if not title:
        s += heading_level * "#" + f" {_paper.ref_code}"
    elif _paper.ref_code in ShortTitles and title:
        s += (
            heading_level * "#" + f" {_paper.ref_code} – {ShortTitles[_paper.ref_code]}"
        )
    else:
        s += heading_level * "#" + f" {_paper.ref_code} – {_paper.title_short}"

    if attribute_tag:
        s += f" {{: #{_paper.ref_code}}}"
    s += "\n\n"

    # Print an info block with all relevant links.
    s += f"> [!info] {_paper.title_short_public}\n> \n"
    s += _glance_links(_paper, prepend="> ")
    s += _pub_links(_paper, prepend="> ")
    s += _email_links(_paper, prepend="> ")

    # Print the following infos line by line.
    s += _submission_status(_paper)
    s += f"**Editorial Board:** {_paper.editorial_board}\n\n"
    s += f"**Contact Editors:** {_paper.contact_editors}\n\n"

    # If submitted, print citation block.
    if _paper.date_submission != "":
        s += "Cite as:\n"
        s += _citation_block(_paper, prepend="> ")

    return s + "\n\n"


def _creation_clock_icon():
    """Print the clock icon with a plus sign (creation date).

    Returns: String with a Markdown span that contains the clock icon.

    """
    return (
        '<span class="md-icon" title="Page created">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M14.47 15.08 11 13V7h1.5v5.25l3.08 1.83c-.41.28-.79.62-1.11 '
        "1m-1.39 4.84c-.36.05-.71.08-1.08.08-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3."
        "58 8 8c0 .37-.03.72-.08 1.08.69.1 1.33.32 1.92.64.1-.56.16-1.13.16-1."
        "72 0-5.5-4.5-10-10-10S2 6.5 2 12s4.47 10 10 10c.59 0 1.16-.06 1.72-.1"
        '6-.32-.59-.54-1.23-.64-1.92M18 15v3h-3v2h3v3h2v-3h3v-2h-3v-3h-2Z">'
        "</path></svg></span>"
    )


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


def _current_time():
    """Return the current time in Europe/Zurich.

    Returns: A string with the current time in Europe/Zurich.

    """
    stamp = datetime.now(tz=ZoneInfo("Europe/Zurich"))
    return stamp.strftime("%d %b %Y, %H:%M")


def print_footer_timestamps(*_files: List[str]):
    """Return the timestamp that goes into the page footers.

    Returns: The code that creates that footer that goes on all markdown
        pages. This includes a span that shows the page creation date and
        the date of the last sync with the GLANCE database.

    """
    repo = git.Git(os.getcwd())

    ti = 0
    for f in _files:
        ti = max(ti, int(repo.log("--max-count=1", "--pretty=format:%ct", f)))

    ti = datetime.fromtimestamp(ti, tz=ZoneInfo("Europe/Zurich")).strftime(
        "%d %b %Y, %H:%M",
    )
    return (
        '</br><aside class="md-source-file"><span class="md-source-file__fact">'
        f"{_creation_clock_icon()}Created: {_current_time()}"
        f"{_update_clock_icon()}Synced with glance: {ti}"
        " (Europe/Zurich)</span></aside>"
    )
