"""Store information about a glance analysis entry.


This module provides a class that stores attributes of an analysis, the full
list is documented in the docstring of the class below. The class can be
instantiated from a CSV file that is pulled from the GLANCE database. The
GLANCE fields are converted into slightly more useful attributes that can be
used to print information about collections of analyses.

Extract table from the glance web UI. All columns listed in the
ANALYSIS_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, validators
from enum import Enum, auto
import logging
import re
from typing import List

from . import subgroups, utils

logger = logging.getLogger(__name__)


ANALYSIS_DATA_COLUMNS = {
    "Reference Code": None,
    "Short Title": None,
    "Public Short Title": None,
    "Full Title": None,
    "Status": None,
    "Run": None,
    "Leading Group": None,
    "Subgroups": None,
    "Contact Editors": None,
    "Supporting Documents": None,
    "Keywords": None,
    "Phase State": None,
    "Phase 0 Start Date": None,
    "Analysis Contacts": None,
    "Analysis Contacts' Start Date": None,
    "Analysis Contacts' End Date": None,
    "Internal Note Editors": None,
    "Editorial Board": None,
    "Chairs": None,
    "Editorial Board Formed On": None,
    "Pre approval Meetings Dates": None,
    "PGC or SGC sign-off date": None,
    "Approval Meetings Dates": None,
}


class AnalysisPubState(Enum):
    """Enum for the publication state of an analysis."""

    CLOSED = auto()
    ONGOING_WO_EB = auto()
    WITH_EB = auto()
    PRE_APPROVED = auto()
    PUB_PREPARATION = auto()
    PAST_PHASE0 = auto()
    UNKNOWN = auto()


@define
class Analysis:
    """A class to hold information about a glance analysis entry.

    Attributes:
        al_analysis_state: String with the analysis-lister analysis state.
        contacts: Comma-separated list of analysis contacts.
        contact_editors: Comma-separated list of contact editors.
        date_approval: String with the approval date.
        date_start: String with the start date.
        date_eb_formed: String with the date on which the EB was formed.
        date_preapproval: String with the  pre-approval date.
        editorial_board: Comma-separated list of EdBoard members.
        glance_url_analysis: String with the analysis GLANCE URL.
        glance_url_publ: String with the publication GLANCE URL.
        int_note_editors: Comma-separated list of INT note editors.
        keywords: List of strings with keywords from GLANCE.
        leading_group: String with the name of the leading physics group.
        ref_code: String with the reference code (no preceding ANA-).
        run: String with the dataset run number the analysis uses.
        phase_state: String with the current phase state.
        status: String with the current status.
        subgroups: Comma-separated list of subgroups the analysis is in.
        supporting_docs: Comma-separated list of links to supporting documents.
        title_full: String with the full title.
        title_public_short: String with the short public title.
        title_short: String with the short title.
        top_subgroups: List of glance.subgroups.Subgroup objects.
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
    glance_url_analysis: str = field(init=False)
    glance_url_publ: str
    int_note_editors: str
    keywords: List[str]
    leading_group: str
    ref_code: str
    run: str
    phase_state: str
    status: str
    subgroups: str
    supporting_docs: str
    title_full: str
    title_public_short: str
    title_short: str
    top_subgroups: List[str] = field(init=False)

    @classmethod
    def from_dict(cls, _dict):
        """Initialise the analysis instance through a dictionary.

        Takes a exported CSV file from GLANCE as input and generates (for one
        line of that CSV file) the corresponding instance of this class.

        Parameters:
            _dict: The dictionary with the info from the CSV file.

        Returns: Instantiated class object.

        """
        return cls(
            contacts=utils.format_contacts(
                _dict["Analysis Contacts"],
                _dict["Analysis Contacts' End Date"],
            ),
            contact_editors=_dict["Contact Editors"],
            date_approval=_dict["Approval Meetings Dates"],
            date_eb_formed=_dict["Editorial Board Formed On"],
            date_start=_dict["Phase 0 Start Date"],
            date_preapproval=_dict["Pre approval Meetings Dates"],
            date_preapproval_signoff=_dict["PGC or SGC sign-off date"],
            editorial_board=utils.format_editorial_board(
                _dict["Editorial Board"],
                _dict["Chairs"],
            ),
            glance_url_publ=None,
            int_note_editors=_dict["Internal Note Editors"],
            keywords=_dict["Keywords"].split(", "),
            leading_group=_dict["Leading Group"],
            ref_code=utils.format_ref_code(_dict["Reference Code"]),
            run=_dict["Run"],
            phase_state=_dict["Phase State"],
            status=_dict["Status"],
            subgroups=re.split(r",(?=\S)", _dict["Subgroups"]),
            supporting_docs=utils.format_supporting_docs(_dict["Supporting Documents"]),
            title_full=_dict["Full Title"],
            title_public_short=_dict["Public Short Title"],
            title_short=_dict["Short Title"],
        )

    def __attrs_post_init__(self):
        """Initialise those attributes derived from others."""
        self.glance_url_analysis = (
            "https://atlas-glance.cern.ch/atlas/analysis/analyses/details.php?"
            f"ref_code=ANA-{self.ref_code}"
        )

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

        logger.debug(f"Analysis {self.ref_code} state: {self.al_analysis_state}")

        # Remove problematic characters from the titles.
        self.title_full = self.title_full.replace("|", "/")
        self.title_public_short = self.title_public_short.replace("|", "/")
        self.title_short = self.title_short.replace("|", "/")

        # Determine the top subgroups this analysis is associated with.
        self.top_subgroups = []
        for group in subgroups.TopGroups:
            if group.id in self.subgroups:
                self.top_subgroups.append(group)
