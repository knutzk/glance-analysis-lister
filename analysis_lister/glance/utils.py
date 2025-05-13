"""Module providing utility functions to handle analysis/paper GLANCE entries.


"""

from attrs import fields as attrs_fields


def format_contacts(contacts: str, end_dates: str) -> str:
    """Return the current analysis contacts of an analysis.

    Parameters:
        contacts: String with all analysis contacts.
        end_dates: String with the end dates per analysis contact.

    Returns: String with comma-separated list of current analysis contacts.

    """
    contacts = contacts.split(", ")
    contacts = [
        contacts[k] for k, d in enumerate(end_dates.split(", ")) if d == "No end date"
    ]
    return ", ".join(contacts)


def format_editorial_board(ed_board: str, chairs: str) -> str:
    """Return the editorial board of an analysis.

    Parameters:
        ed_board: String with all Editorial Board members.
        chairs: String with all (Editorial Board) Chairs.

    Returns: String with comma-separated list of editorial board members. The
        editorial board chair is marked with "(chair)" in that list.

    """
    if ed_board == "":
        return ""

    ed_board = [x.strip() for x in ed_board.split(",")]
    chairs = [x.strip() for x in chairs.split(",")]
    ed_board = [f"**{x}** (chair)" if x in chairs else x for x in ed_board]
    return ", ".join(ed_board)


def format_ref_code(ref_code: str) -> str:
    """Return the reference code of an analysis/paper.

    Parameters:
        ref_code: String with reference code as stored in the GLANCE entry.

    Returns: Reference code but with prepended "ANA-" removed if present.

    """
    if ref_code.startswith("ANA-"):
        ref_code = ref_code[4:]

    return ref_code


def format_supporting_docs(supporting_docs: str) -> str:
    """Return comma-separated list of supporting documents.

    Parameters:
        supporting_docs: String with the docs as stored in the GLANCE entry.

    Returns: Comma-separated list of supporting documents.

    """
    if supporting_docs != "":
        supporting_docs = supporting_docs.split(",")

    return supporting_docs


def format_url_doi(urls: str) -> str:
    """Return the DOI URL of a paper.

    Parameters:
        urls: String with a list of URLs (comma-separated or not).

    Returns: String with the DOI URL.

    """
    urls = ["http" + x for x in urls.split("http")[1:]]
    urls = list(filter(lambda a: "doi.org" in a, urls))
    return urls[0] if urls else ""


def format_url_inspire(urls: str) -> str:
    """Return the Inspire HEP URL of a paper.

    Parameters:
        urls: String with a list of URLs (comma-separated or not).

    Returns: String with the Inspire HEP URL.

    """
    urls = ["http" + x for x in urls.split("http")[1:]]
    urls = list(filter(lambda a: "inspirehep.net" in a, urls))
    return urls[0] if urls else ""


def get_init_fields(source_obj, target_cls):
    """Return a dict of field values from source_obj that are init=True in target_cls.

    Parameters:
        source_obj: The source object from which to extract field values.
        target_cls: The target class whose fields are to be matched.

    Returns: A dictionary with field names as keys and their corresponding values from
    source_obj.

    """
    target_init_fields = {f.name for f in attrs_fields(target_cls) if f.init}
    return {
        name: getattr(source_obj, name)
        for name in target_init_fields
        if hasattr(source_obj, name)
    }


def glance_analysis_url(ref_code: str) -> str:
    """Return the GLANCE URL of an analysis.

    Parameters:
        ref_code: String with the reference code of the analysis.

    Returns: String with the GLANCE URL of the analysis.

    """
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/analyses/details.php?"
        f"ref_code=ANA-{ref_code}"
    )


def glance_paper_url(ref_code: str) -> str:
    """Return the GLANCE URL of a paper.

    Parameters:
        ref_code: String with the reference code of the paper.

    Returns: String with the GLANCE URL of the paper.

    """
    return (
        "https://atlas-glance.cern.ch/atlas/analysis/papers/details.php?"
        f"ref_code={ref_code}"
    )


def clean_titles(*titles: str) -> list[str]:
    """Clean the titles of an analysis/publication.

    Parameters:
        titles: Tuple with the different title strings.

    Returns: List with the cleaned titles.

    """
    return [t.replace("|", "/") for t in titles]


def get_top_subgroups(subgroup_ids: list[str], topgroups: list) -> list:
    """Return the top subgroups of a list of subgroups.

    Parameters:
        subgroup_ids: List with the IDs of the subgroups.
        topgroups: List with the top groups.

    Returns: List with the top subgroups.

    """
    return [group for group in topgroups if group.id in subgroup_ids]
