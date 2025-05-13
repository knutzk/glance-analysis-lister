"""Store information about papers from glance.


Extract table from GLANCE web UI. All columns listed in the
PAPER_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, validators
import logging

from ..lookup_dicts import journal_refs

from . import utils
from .enums import PaperPubState
from .glance_base import GlanceEntry

logger = logging.getLogger(__name__)


PAPER_DATA_COLUMNS = {
    "Reference Code": None,
    "Short Title": None,
    "Public Short Title": None,
    "Full Title": None,
    "Status": None,
    "Phase State": None,
    "Run": None,
    "Leading Group": None,
    "Subgroups": None,
    "Supporting Documents": None,
    "Current Paper Draft": None,
    "Contact Editors": None,
    "Keywords": None,
    "Phase 1 Start Date": None,
    "Editorial Board": None,
    "Chairs": None,
    "ArXiv Reference Number": None,
    "ArXiv Reference URLs": None,
    "Figures": None,
    "Final Title (Tex)": None,
    "Journal of Final Submission": None,
    "arXiv Submission Date": None,
    "Journal Acceptance Date": None,
    "Final Journal Publication URLs": None,
    "Publication Date": None,
}


@define
class Paper(GlanceEntry):
    """A class to hold information about a glance paper entry.

    Attributes:
        al_pub_state: Enum for the publication state of the paper.
        arxiv_number: String with the arXiv number of the paper.
        arxiv_url: String with the arXiv URL of the paper.
        contact_editors: String with the contact editors of the paper.
        date_acceptance: String with the journal acceptance date.
        date_phase_one: String with the phase 1 start date.
        date_publication: String with the publication date.
        date_submission: String with the arXiv submission date.
        doi: String with the DOI of the paper.
        doi_url: String with the DOI URL of the paper.
        editorial_board: String with the editorial board of the paper.
        figure_url: String with the figure URL of the paper.
        glance_url_publ: String with the glance URL of the paper.
        inspire_url: String with the inspire URL of the paper.
        journal: String with the journal of final submission.
        journal_ref: String with the journal reference of the paper.
        run: String with the run of the paper.
        title_final_tex: String with the final title in TeX format.

    """

    al_pub_state: PaperPubState = field(
        validator=validators.instance_of(PaperPubState), init=False
    )
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
    glance_url_publ: str = field(init=False)
    inspire_url: str
    journal: str
    journal_ref: str = field(init=False)
    run: str
    title_final_tex: str

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
                _dict["Final Journal Publication URLs"]
            ),
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
        super().__attrs_post_init__()

        self.doi = self.doi_url[self.doi_url.find("doi.org") + 8 :]
        self.glance_url_publ = utils.glance_paper_url(self.ref_code)

        # Determine the paper publication state. If phase 1 or phase 2 are active,
        # the paper is considered ongoing (which means that the corresponding
        # analysis entry will be listed). )
        if self.status == " Phase 1 is  Active ":
            self.al_pub_state = PaperPubState.ONGOING
        elif self.status == " Phase 2 is  Active ":
            self.al_pub_state = PaperPubState.ONGOING
        elif self.date_submission != "" and self.date_publication == "":
            self.al_pub_state = PaperPubState.SUBMITTED
        elif self.date_publication != "":
            self.al_pub_state = PaperPubState.PUBLISHED
        else:
            self.al_pub_state = PaperPubState.UNKNOWN

        logger.debug("Paper %s state %s", self.ref_code, self.al_pub_state)

        if self.al_pub_state == PaperPubState.SUBMITTED and self.journal != "":
            self.journal_ref = f"Submitted to {self.journal}"
        elif self.doi in journal_refs.JournalRefs:
            self.journal_ref = journal_refs.JournalRefs[self.doi]
        else:
            self.journal_ref = ""

        if self.journal_ref == "" and self.doi != "":
            logger.warning("No journal reference found for DOI: %s", self.doi)
