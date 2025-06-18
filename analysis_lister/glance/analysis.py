"""Store information about a glance analysis entry.


This module provides a class that stores attributes of an analysis. The class
gets instantiated with a CSV file scraped from the GLANCE web interface. The
list of required fields is stored in .field_maps.REQUIRED_COLUMNS_ANALYSIS.

Most attributes are direct translations of the column names in the CSV file,
others require more intricate parsing, handled in the post-init method.

"""

from attrs import define, field, validators
import logging
from typing import List

from .enums import PublicationState, SoftwareRelease
from .field_maps import FIELD_MAP_ANALYSIS
from .utils import (
    clean_titles,
    format_contacts,
    format_editorial_board,
    glance_analysis_url,
)

logger = logging.getLogger(__name__)


@define
class Analysis:
    """A class to hold information about a glance analysis entry.

    Attributes:
        contact_editors: String with the contact editors.
        contacts: String with the analysis contacts.
        date_approval: String with the date of approval meetings.
        date_eb_formed: String with the date when editorial board was formed.
        date_preapproval_signoff: String with the date of sign-off by PGC or SGC.
        date_preapproval: String with the date of pre-approval meetings.
        date_start: String with the start date of phase 0.
        editorial_board: String with the editorial board members.
        glance_url_analysis: String with the URL to the analysis in GLANCE.
        glance_url_publ: String with the URL to the publication in GLANCE.
        int_note_editors: String with internal note editors.
        keywords: List of keywords associated with the analysis.
        leading_group: String with the leading group.
        phase_state: String with the phase state.
        pub_state: Enum for the publication state of the analysis.
        ref_code: String with the reference code.
        run: String with the run number.
        software_release: Enum with the software release of the analysis.
        status: String with the status of the analysis.
        subgroups: List of subgroups associated with the analysis.
        supporting_docs: String with supporting documents.
        title_full: String with the full title of the analysis.
        title_short_public: String with the short public title of the analysis.
        title_short: String with the short title of the analysis.

    """

    contact_editors: str
    contacts: str
    date_approval: str
    date_eb_formed: str
    date_preapproval_signoff: str
    date_preapproval: str
    date_start: str
    editorial_board: str
    glance_url_analysis: str = field(init=False)
    glance_url_publ: str
    int_note_editors: str
    keywords: List[str]
    leading_group: str
    phase_state: str
    pub_state: PublicationState = field(
        validator=validators.instance_of(PublicationState), init=False
    )
    ref_code: str
    run: str
    software_release: SoftwareRelease = field(
        validator=validators.instance_of(SoftwareRelease), init=False
    )
    status: str
    subgroups: List[str]
    supporting_docs: str
    title_full: str
    title_short_public: str
    title_short: str

    @classmethod
    def from_csv_dict(cls, _dict):
        """Initialise the analysis instance through a dictionary.

        Args:
            _dict (dict): Dictionary containing the analysis data.

        Returns:
            Analysis: An instance of the Analysis class.

        """
        parsed = {}
        for key, (col, func) in FIELD_MAP_ANALYSIS.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        # special fields with multi-column dependencies
        parsed["contacts"] = format_contacts(
            _dict["Analysis Contacts"], _dict["Analysis Contacts' End Date"]
        )
        parsed["editorial_board"] = format_editorial_board(
            _dict["Editorial Board"], _dict["Chairs"]
        )
        parsed["glance_url_publ"] = None

        return cls(**parsed)

    @classmethod
    def from_json(cls, data: dict) -> "Analysis":
        data = data.copy()
        data.pop("glance_url_analysis", None)
        data.pop("pub_state", None)
        data.pop("software_release", None)

        return cls(**data)

    def determine_release(self):
        """Get the software release associated with the analysis.

        Returns:
            str: The software release associated with the analysis.

        """
        if "R22" in self.keywords:
            return SoftwareRelease.R25
        elif "R21" in self.keywords:
            return SoftwareRelease.R21
        else:
            return SoftwareRelease.UNKNOWN

    def determine_status(self):
        """Determine the publication status of the analysis.

        The status is determined based on the values of various attributes,
        e.g., whether the analysis is closed, in phase 0, or whether its
        preapproval sign-off has been completed.

        Returns:
            PublicationState: The publication state of the analysis.

        """
        if self.status == " Analysis is  Closed ":
            return PublicationState.CLOSED
        elif self.status == " Phase 0 is  Finished ":
            return PublicationState.PAST_PHASE0
        elif self.date_preapproval_signoff != "":
            return PublicationState.PREAPPROVED
        elif self.date_eb_formed != "":
            return PublicationState.ONGOING_WITH_EB
        elif self.status == " Phase 0 is  Active ":
            return PublicationState.ONGOING_WO_EB
        else:
            logger.error("Unknown analysis state for analysis %s", self.ref_code)
            return PublicationState.UNKNOWN

    def is_ongoing(self) -> bool:
        """Check if the analysis is ongoing.

        The following states are considered ongoing:
        - ONGOING_WITH_EB
        - ONGOING_WO_EB
        - PREAPPROVED
        - PHASE1_OR_2

        Returns:
            bool: True if the analysis is ongoing, False otherwise.

        """
        return self.pub_state in {
            PublicationState.ONGOING_WITH_EB,
            PublicationState.ONGOING_WO_EB,
            PublicationState.PREAPPROVED,
            PublicationState.PHASE1_OR_2,
        }

    def __attrs_post_init__(self):
        """Post-initialization of analysis instance."""
        self.glance_url_analysis = glance_analysis_url(self.ref_code)
        self.title_full, self.title_short, self.title_short_public = clean_titles(
            self.title_full, self.title_short, self.title_short_public
        )

        # Determine the publication state of the analysis.
        self.pub_state = self.determine_status()
        logger.debug("Analysis %s state: %s", self.ref_code, self.pub_state)

        # Determine the software release of the analysis.
        self.software_release = self.determine_release()
        logger.debug(
            "Analysis %s software release: %s", self.ref_code, self.software_release
        )
