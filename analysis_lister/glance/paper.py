"""Store information about papers from glance.


Extract table from the glance web UI with the following columns:
  - "Reference Code"
  - "Short Title"
  - "Public Short Title"
  - "Full Title"
  - "Status"
  - "Phase State"
  - "Run"
  - "Leading Group"
  - "Subgroups"
  - "Supporting Documents"
  - "Current Paper Draft"
  - "Contact Editors"
  - "Keywords"
  - "Phase 1 Start Date"
  - "Editorial Board"
  - "Chairs"
  - "ArXiv Reference Number"
  - "ArXiv Reference URLs"
  - "Figures"
  - "Final Title (Tex)"
  - "Journal of Final Submission"
  - "arXiv Submission Date"
  - "Journal Acceptance Date"
  - "Final Journal Publication URLs"
  - "Publication Date"

"""

from attrs import define, field
from typing import List

from ..lookup_dicts import journal_refs

from . import subgroups, utils


@define
class Paper:
    """A class to hold information about a glance paper entry.

    Attributes:
        arxiv_number: String with the arXiv identifier of the paper.
        arxiv_url: String with the URL to the arXiv entry.
        contact_editors: Comma-separated list of contact editors.
        date_acceptance: String with the journal acceptance date.
        date_phase_one: String with the start date of Phase 1.
        date_publication: String with the publication date of the paper.
        date_submission: String with the (arXiv) submission date of the paper.
        doi: String with the DOI identifier.
        doi_url: String with the DOI identifier converted to an http link.
        editorial_board: Comma-separated list of EdBoard members.
        figure_url: String with the URL to the figures webpage.
        glance_url_analysis: String with the analysis GLANCE URL.
        glance_url_paper: String with the paper GLANCE URL.
        inspire_url: String with the Inspire HEP URL.
        is_published: Boolean whether the paper is published.
        is_submitted: Boolean whether the paper is submitted.
        journal: String with the name of the journal of publication.
        journal_ref: String that holds the full journal reference.
        keywords: List of strings with keywords from GLANCE.
        phase_state: String with the "Phase State" field from GLANCE.
        ref_code: String with the paper reference code.
        run: String with the dataset run number used for the paper.
        status: String with the "Status" field from GLANCE.
        subgroups: Comma-separated list of subgroups associated to the paper.
        title_final_tex: String with the final title in TeX format.
        title_full: String with the full title.
        title_short_public: String with the short public title.
        title_short: String with the short title.
        top_subgroups: List of glance.subgroups.Subgroup objects.
    """

    arxiv_number: str
    arxiv_url: str
    contact_editors: str
    date_acceptance: str
    date_phase_one: str
    date_publication: str
    date_submission: str
    doi: str = field(init=False)
    doi_url: str
    editorial_board: str
    figure_url: str
    glance_url_analysis: str = field(init=False)
    glance_url_paper: str = field(init=False)
    inspire_url: str
    is_published: bool
    is_submitted: bool
    journal: str
    journal_ref: str = field(init=False)
    keywords: List[str]
    phase_state: str
    ref_code: str
    run: str
    status: str
    subgroups: str
    title_final_tex: str
    title_full: str
    title_short: str
    title_short_public: str
    top_subgroups: List[str] = field(init=False)

    @classmethod
    def from_dict(cls, _dict):
        """Initialise the paper instance through a dictionary.

        Takes a exported CSV file from GLANCE as input and generates (for one
        line of that CSV file) the corresponding instance of this class.

        Parameters:
            _dict: The dictionary with the info from the CSV file.

        Returns: Instantiated class object.

        """
        return cls(
            arxiv_number=_dict["ArXiv Reference Number"],
            arxiv_url=_dict["ArXiv Reference URLs"],
            contact_editors=_dict["Contact Editors"],
            date_acceptance=_dict["Journal Acceptance Date"],
            date_phase_one=_dict["Phase 1 Start Date"],
            date_publication=_dict["Publication Date"],
            date_submission=_dict["arXiv Submission Date"],
            doi_url=utils.format_url_doi(_dict["Final Journal Publication URLs"]),
            editorial_board=utils.format_editorial_board(
                _dict["Editorial Board"],
                _dict["Chairs"],
            ),
            figure_url=_dict["Figures"],
            inspire_url=utils.format_url_inspire(
                _dict["Final Journal Publication URLs"],
            ),
            is_published=_dict["Publication Date"] != "",
            is_submitted=_dict["arXiv Submission Date"] != "",
            journal=_dict["Journal of Final Submission"],
            keywords=_dict["Keywords"].split(", "),
            phase_state=_dict["Phase State"],
            ref_code=_dict["Reference Code"],
            run=_dict["Run"],
            status=_dict["Status"],
            subgroups=_dict["Subgroups"].split(","),
            title_final_tex=_dict["Final Title (Tex)"],
            title_full=_dict["Full Title"],
            title_short=_dict["Short Title"],
            title_short_public=_dict["Public Short Title"],
        )

    def __attrs_post_init__(self):
        """Initialise those attributes derived from others."""
        # Determine the DOI from the DOI URL.
        self.doi = self.doi_url[self.doi_url.find("doi.org") + 8 :]

        # Determine the GLANCE URLs for analysis and paper.
        self.glance_url_analysis = (
            "https://atlas-glance.cern.ch/atlas/analysis/analyses/details.php?"
            f"ref_code=ANA-{self.ref_code}"
        )
        self.glance_url_paper = (
            "https://atlas-glance.cern.ch/atlas/analysis/papers/details.php?"
            f"ref_code={self.ref_code}"
        )

        # Determine the journal reference string.
        if self.is_submitted and not self.is_published and self.journal != "":
            self.journal_ref = f"Submitted to {self.journal}"
        elif self.doi in journal_refs.JournalRefs:
            self.journal_ref = journal_refs.JournalRefs[self.doi]
        else:
            self.journal_ref = ""

        if self.journal_ref == "" and self.doi != "":
            print("No journal reference found for DOI:", self.doi)

        # Determine the top subgroups this paper is associated with.
        self.top_subgroups = []
        for group in subgroups.TopGroups:
            if group.id in self.subgroups:
                self.top_subgroups.append(group)
