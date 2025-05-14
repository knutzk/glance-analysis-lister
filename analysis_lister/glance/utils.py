"""Module providing utility functions to handle analysis/paper GLANCE entries.


"""

from attrs import fields as attrs_fields


def format_contacts(contacts: str, end_dates: str) -> str:
    """Return the current analysis contacts of an analysis."""
    contacts = contacts.split(", ")
    contacts = [
        contacts[k] for k, d in enumerate(end_dates.split(", ")) if d == "No end date"
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


def format_ref_code(ref_code: str) -> str:
    """Return the reference code of an analysis/paper."""
    if ref_code.startswith("ANA-"):
        ref_code = ref_code[4:]

    return ref_code


def format_supporting_docs(supporting_docs: str) -> str:
    """Return comma-separated list of supporting documents."""
    if supporting_docs != "":
        supporting_docs = supporting_docs.split(",")

    return supporting_docs


def format_url_doi(urls: str) -> str:
    """Return the DOI URL of a paper."""
    urls = ["http" + x for x in urls.split("http")[1:]]
    urls = list(filter(lambda a: "doi.org" in a, urls))
    return urls[0] if urls else ""


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
