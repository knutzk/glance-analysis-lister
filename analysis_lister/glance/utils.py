"""Module providing utility functions to handle analysis/paper GLANCE entries.


"""

from attrs import fields as attrs_fields
import logging
import re

logger = logging.getLogger(__name__)


def format_contacts(contacts: str, end_dates: str) -> str:
    """Return the current analysis contacts of an analysis."""
    contacts = contacts.split(", ")
    end_dates = end_dates.split(", ")
    if len(contacts) != len(end_dates):
        logger.warning("Cannot resolve analysis contacts: %s.", contacts)

    contacts = [c for c, d in zip(contacts, end_dates) if d == "No end date"]
    return ", ".join(contacts)


def format_editorial_board(ed_board: str, chairs: str) -> str:
    """Return the editorial board of an analysis, with chairs highlighted."""
    if ed_board == "":
        return ""

    ed_board = [x.strip() for x in ed_board.split(",")]
    chairs = [x.strip() for x in chairs.split(",")]
    ed_board = [f"**{x}** (chair)" if x in chairs else x for x in ed_board]
    return ", ".join(ed_board)


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


def format_supporting_docs(supporting_docs: str) -> str:
    """Return comma-separated list of supporting documents."""
    if supporting_docs != "":
        supporting_docs = supporting_docs.split(",")

    return supporting_docs


# Patterns to recover the publication date that a publisher encodes in its
# DOIs. GLANCE lists the DOIs of a paper and of its erratum/addendum in
# arbitrary order, so they have to be sorted by publication date to tell the
# original article from the later correction.
_DOI_DATE_PATTERNS = (
    # JHEP, e.g. 10.1007/JHEP07(2023)203
    re.compile(r"/JHEP(?P<month>\d{2})\((?P<year>\d{4})\)"),
    # Springer EPJ, e.g. 10.1140/epjc/s10052-023-11573-0 (year modulo 1000)
    re.compile(r"/epj\w*/s\d+-(?P<year>\d{3})-"),
    # Elsevier, e.g. 10.1016/j.physletb.2022.137379
    re.compile(r"^10\.1016/j\.\w+\.(?P<year>\d{4})\."),
)


def doi_from_url(url: str) -> str:
    """Return the bare DOI of a doi.org URL (empty string if there is none)."""
    index = url.find("doi.org/")
    return url[index + 8 :] if index >= 0 else ""


def _doi_date(doi: str) -> tuple[int, int]:
    """Return the (year, month) encoded in a DOI, or (0, 0) if undecodable."""
    for pattern in _DOI_DATE_PATTERNS:
        match = pattern.search(doi)
        if not match:
            continue

        year = int(match.group("year"))
        if year < 1000:  # Springer writes the year modulo 1000.
            year += 2000

        groups = match.groupdict()
        return year, int(groups.get("month") or 0)

    return 0, 0


def format_url_dois(url_str: str) -> list[str]:
    """Return the DOI URLs of a paper, earliest publication first.

    A paper carries more than one DOI once an erratum or an addendum has been
    published: the journal assigns those their own DOI and GLANCE lists them
    alongside the original one. The list is therefore ordered by the
    publication date encoded in the DOI, so that the original article comes
    first and any correction follows.

    """
    urls = ["http" + x for x in url_str.split("http")[1:]]
    urls = [u for u in urls if "doi.org/" in u]

    # The same DOI may be listed several times, and under both the doi.org and
    # the dx.doi.org host. Deduplicate on the DOI, keeping the first URL.
    by_doi: dict[str, str] = {}
    for url in urls:
        by_doi.setdefault(doi_from_url(url), url)

    if len(by_doi) > 1 and any(_doi_date(doi) == (0, 0) for doi in by_doi):
        logger.warning(
            "No publication date encoded in all of these DOIs, cannot tell "
            "the original paper from an erratum: %s",
            list(by_doi),
        )

    # sorted() is stable, so DOIs without a decodable date keep GLANCE's order.
    return sorted(by_doi.values(), key=lambda u: _doi_date(doi_from_url(u)))


def format_url_inspire(urls: str) -> str:
    """Return the Inspire HEP URL of a paper."""
    urls = ["http" + x for x in urls.split("http")[1:]]
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
