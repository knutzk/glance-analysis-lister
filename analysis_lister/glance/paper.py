"""Store information about papers from glance.


Extract table from GLANCE web UI. All columns listed in the
fields.PAPER_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field
import logging

from ..lookup_dicts import journal_refs

from . import utils
from .analysis import Analysis
from .enums import PublicationState
from .field_maps import FIELD_MAP_PAPER
from .utils import get_init_fields

logger = logging.getLogger(__name__)


@define
class Paper(Analysis):
    """A class representing a published analysis with additional paper metadata.

    Attributes:
        arxiv_number: String with the arXiv number of the paper.
        arxiv_url: String with the arXiv URL of the paper.
        date_acceptance: String with the journal acceptance date.
        date_phase_one: String with the phase 1 start date.
        date_publication: String with the publication date.
        date_submission: String with the arXiv submission date.
        doi: String with the DOI of the paper.
        doi_url: String with the DOI URL of the paper.
        figure_url: String with the figure URL of the paper.
        glance_url_publ: String with the glance URL of the paper.
        inspire_url: String with the inspire URL of the paper.
        journal: String with the journal of final submission.
        journal_ref: String with the journal reference of the paper.
        status_paper: String with the status of the paper.
        title_final_tex: String with the final title in TeX format.

    """

    arxiv_number: str
    arxiv_url: str
    date_acceptance: str
    date_phase_one: str
    date_publication: str
    date_submission: str
    doi: str = field(init=False)
    doi_url: str
    figure_url: str
    glance_url_publ: str = field(init=False)
    inspire_url: str
    journal: str
    journal_ref: str = field(init=False)
    status_paper: str
    title_final_tex: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a Paper instance from an analysis and a dictionary."""
        paper_fields = {}
        for key, (col, func) in FIELD_MAP_PAPER.items():
            raw = _dict.get(col, "") if col else ""
            paper_fields[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **paper_fields)

    def __attrs_post_init__(self):
        """Post-initialization of paper instance."""
        super().__attrs_post_init__()

        self.doi = self.doi_url[self.doi_url.find("doi.org") + 8 :]
        self.glance_url_publ = utils.glance_paper_url(self.ref_code)

        # Determine the paper publication state. If phase 1 or phase 2 are active,
        # the paper is considered ongoing (which means that the corresponding
        # analysis entry will be listed). )
        if self.status_paper == " Phase 1 is  Active ":
            self.pub_state = PublicationState.PHASE1_OR_2
        elif self.status_paper == " Phase 2 is  Active ":
            self.pub_state = PublicationState.PHASE1_OR_2
        elif self.date_submission and not self.date_publication:
            self.pub_state = PublicationState.SUBMITTED_TO_JOURNAL
        elif self.date_publication:
            self.pub_state = PublicationState.PUBLISHED
        else:
            self.pub_state = PublicationState.UNKNOWN
            logger.error("Paper %s has unknown publication state", self.ref_code)

        logger.debug("Paper %s state %s", self.ref_code, self.pub_state)

        if self.pub_state == PublicationState.SUBMITTED_TO_JOURNAL and self.journal:
            self.journal_ref = f"Submitted to {self.journal}"
        elif self.doi in journal_refs.JournalRefs:
            self.journal_ref = journal_refs.JournalRefs[self.doi]
        else:
            self.journal_ref = ""

        if not self.journal_ref and self.doi:
            logger.warning("No journal reference found for DOI: %s", self.doi)
