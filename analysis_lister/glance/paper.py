"""Store information about papers from glance.


Extract table from GLANCE web UI. All columns listed in the
fields.PAPER_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, validators
import logging

from ..lookup_dicts import journal_refs

from . import utils
from .glance_base import GlanceEntry
from .enums import PaperPubState
from .field_maps import FIELD_MAP_PAPER

logger = logging.getLogger(__name__)


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
        """Initialise the paper instance through a dictionary."""
        parsed = {}
        for key, (col, func) in FIELD_MAP_PAPER.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        # custom fields
        parsed["editorial_board"] = utils.format_editorial_board(
            _dict["Editorial Board"], _dict["Chairs"]
        )

        return cls(**parsed)

    def __attrs_post_init__(self):
        """Post-initialization of paper instance."""
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
        elif self.date_submission and not self.date_publication:
            self.al_pub_state = PaperPubState.SUBMITTED
        elif self.date_publication:
            self.al_pub_state = PaperPubState.PUBLISHED
        else:
            self.al_pub_state = PaperPubState.UNKNOWN

        logger.debug("Paper %s state %s", self.ref_code, self.al_pub_state)

        if self.al_pub_state == PaperPubState.SUBMITTED and self.journal:
            self.journal_ref = f"Submitted to {self.journal}"
        elif self.doi in journal_refs.JournalRefs:
            self.journal_ref = journal_refs.JournalRefs[self.doi]
        else:
            self.journal_ref = ""

        if not self.journal_ref and self.doi:
            logger.warning("No journal reference found for DOI: %s", self.doi)
