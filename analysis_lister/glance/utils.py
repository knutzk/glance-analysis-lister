"""Module providing utility functions to handle analysis/paper GLANCE entries.


"""

import logging
import re

from attrs import fields as attrs_fields

from ..lookup_dicts.doi_order import DoiOrder

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
    """Extract DOI URLs; Paper construction resolves their citation order."""
    # GLANCE concatenates the URLs without a separator, so splitting on the
    # scheme is all there is to go by. Stripping guards the journal_refs
    # lookup, which a trailing space would silently turn into a miss.
    urls = ["http" + x.strip() for x in url_str.split("http")[1:]]
    return [u for u in urls if "doi.org/" in u]


def order_doi_urls(urls: list[str], ref_code: str) -> list[str]:
    """Deduplicate and order DOIs, warning when dates cannot resolve the order.

    Missing months cover the entire year, so they overlap any dated DOI in
    that year. Unknown or overlapping dates retain input order unless a
    verified override supplies the full order. Used for CSV and JSON loads.
    """

    # The same DOI may be listed several times, and under both the doi.org and
    # the dx.doi.org host. Deduplicate on the DOI, keeping the first URL.
    by_doi: dict[str, str] = {}
    for url in urls:
        by_doi.setdefault(doi_from_url(url), url)

    override = DoiOrder.get(ref_code)
    if override is not None:
        if len(override) != len(set(override)) or set(override) != set(by_doi):
            raise ValueError(
                f"{ref_code}: DOI order override does not match the record; "
                "update lookup_dicts/doi_order.py"
            )
        return [by_doi[doi] for doi in override]

    dates = [_doi_date(doi) for doi in by_doi]
    ambiguous = any(date == (0, 0) for date in dates) or any(
        year == other_year and (not month or not other_month or month == other_month)
        for i, (year, month) in enumerate(dates)
        for other_year, other_month in dates[i + 1 :]
    )
    if len(by_doi) > 1 and ambiguous:
        logger.warning(
            "%s: ambiguous DOI order (unknown or overlapping dates); keeping "
            "input order. Verify the original article and add an override in "
            "lookup_dicts/doi_order.py: %s",
            ref_code,
            list(by_doi),
        )
        return list(by_doi.values())

    return sorted(by_doi.values(), key=lambda u: _doi_date(doi_from_url(u)))


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
