"""Store information about a glance analysis entry.


This module provides a class that stores attributes of an analysis, the full
list is documented in the docstring of the class below. The class can be
instantiated from a CSV file that is pulled from the GLANCE database. The
GLANCE fields are converted into slightly more useful attributes that can be
used to print information about collections of analyses.

Extract table from the glance web UI. All columns listed in the
fields.ANALYSIS_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, validators
import logging

from . import utils
from .enums import AnalysisPubState
from .glance_base import GlanceEntry
from .field_maps import FIELD_MAP_ANALYSIS

logger = logging.getLogger(__name__)


@define
class Analysis(GlanceEntry):
    """A class to hold information about a glance analysis entry.

    Attributes:
        al_analysis_state: Enum for the publication state of the analysis.
        contacts: String with the analysis contacts.
        contact_editors: String with the contact editors.
        date_approval: String with the date of approval meetings.
        date_start: String with the start date of phase 0.
        date_eb_formed: String with the date when editorial board was formed.
        date_preapproval: String with the date of pre-approval meetings.
        date_preapproval_signoff: String with the date of sign-off by PGC or SGC.
        editorial_board: String with the editorial board members.
        glance_url_publ: String with the URL to the publication in GLANCE.
        int_note_editors: String with internal note editors.
        leading_group: String with the leading group.
        run: String with the run number.
        supporting_docs: String with supporting documents.

    """

    al_analysis_state: AnalysisPubState = field(
        validator=validators.instance_of(AnalysisPubState), init=False
    )
    contacts: str
    contact_editors: str
    date_approval: str
    date_start: str
    date_eb_formed: str
    date_preapproval: str
    date_preapproval_signoff: str
    editorial_board: str
    glance_url_publ: str
    int_note_editors: str
    leading_group: str
    run: str
    supporting_docs: str

    @classmethod
    def from_dict(cls, _dict):
        """Initialise the analysis instance through a dictionary."""
        parsed = {}
        for key, (col, func) in FIELD_MAP_ANALYSIS.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        # special fields with multi-column dependencies
        parsed["contacts"] = utils.format_contacts(
            _dict["Analysis Contacts"], _dict["Analysis Contacts' End Date"]
        )
        parsed["editorial_board"] = utils.format_editorial_board(
            _dict["Editorial Board"], _dict["Chairs"]
        )
        parsed["glance_url_publ"] = None

        return cls(**parsed)

    def __attrs_post_init__(self):
        """Post-initialisation of the analysis instance."""
        super().__attrs_post_init__()

        # Determine the state of the analysis.
        if self.status == " Analysis is  Closed ":
            self.al_analysis_state = AnalysisPubState.CLOSED
        elif self.status == " Phase 0 is  Finished ":
            self.al_analysis_state = AnalysisPubState.PAST_PHASE0
        elif self.date_preapproval_signoff != "":
            self.al_analysis_state = AnalysisPubState.PRE_APPROVED
        elif self.date_eb_formed != "":
            self.al_analysis_state = AnalysisPubState.WITH_EB
        elif self.status == " Phase 0 is  Active ":
            self.al_analysis_state = AnalysisPubState.ONGOING_WO_EB
        else:
            self.al_analysis_state = AnalysisPubState.UNKNOWN
            logger.error("Unknown analysis state for analysis %s", self.ref_code)

        logger.debug("Analysis %s state: %s", self.ref_code, self.al_analysis_state)
