"""Store information about a glance analysis entry.


This module provides a class that stores attributes of an analysis, the full
list is documented in the docstring of the class below. The class can be
instantiated from a CSV file that is pulled from the GLANCE database. The
GLANCE fields are converted into slightly more useful attributes that can be
used to print information about collections of analyses.


Extract table from the glance web UI with the following columns:
  - "Reference Code"
  - "Short Title"
  - "Public Short Title"
  - "Full Title"
  - "Status"
  - "Run"
  - "Leading Group"
  - "Subgroups"
  - "Contact Editors"
  - "Supporting Documents"
  - "Keywords"
  - "Phase State"
  - "Phase 0 Start Date"
  - "Analysis Contacts"
  - "Analysis Contacts' Start Date"
  - "Analysis Contacts' End Date"
  - "Internal Note Editors"
  - "Editorial Board"
  - "Chairs"
  - "Editorial Board Formed On"
  - "Pre approval Meetings Dates"
  - "Approval Meetings Dates"

"""

from attrs import define, field
from typing import List

from . import subgroups, utils


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
    "Approval Meetings Dates": None,
}


@define
class Analysis:
    """A class to hold information about a glance analysis entry.

    Attributes:
        contacts: Comma-separated list of analysis contacts.
        contact_editors: Comma-separated list of contact editors.
        date_approval: String with the approval date.
        date_start: String with the start date.
        date_eb_formed: String with the date on which the EB was formed.
        date_preapproval: String with the  pre-approval date.
        editorial_board: Comma-separated list of EdBoard members.
        glance_url_analysis: String with the analysis GLANCE URL.
        glance_url_paper: String with the paper GLANCE URL.
        int_note_editors: Comma-separated list of INT note editors.
        is_approved: Boolean whether the analysis is approved.
        is_closed: Boolean whether the analysis is closed.
        is_in_phase0: Boolean whether analysis is in the Phase 0 state.
        is_preapproved: Boolean whether analysis is pre-approved.
        is_with_edboard: Boolean whether an EdBoard is assigned to the analysis.
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

    contacts: str
    contact_editors: str
    date_approval: str
    date_start: str
    date_eb_formed: str
    date_preapproval: str
    editorial_board: str
    glance_url_analysis: str = field(init=False)
    glance_url_paper: str = field(init=False)
    int_note_editors: str
    is_approved: str
    is_closed: str
    is_in_phase0: bool
    is_preapproved: bool
    is_with_edboard: bool
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
            editorial_board=utils.format_editorial_board(
                _dict["Editorial Board"],
                _dict["Chairs"],
            ),
            int_note_editors=_dict["Internal Note Editors"],
            is_approved=_dict["Status"] == " Phase 0 is  Finished ",
            is_closed=_dict["Status"] == " Analysis is  Closed ",
            is_in_phase0=_dict["Status"] == " Phase 0 is  Active ",
            is_preapproved=_dict["Pre approval Meetings Dates"] != "",
            is_with_edboard=_dict["Editorial Board Formed On"] != "",
            keywords=_dict["Keywords"].split(", "),
            leading_group=_dict["Leading Group"],
            ref_code=utils.format_ref_code(_dict["Reference Code"]),
            run=_dict["Run"],
            phase_state=_dict["Phase State"],
            status=_dict["Status"],
            subgroups=_dict["Subgroups"].split(","),
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
        self.glance_url_paper = (
            "https://atlas-glance.cern.ch/atlas/analysis/papers/details.php?"
            f"ref_code={self.ref_code}"
        )

        # Determine the top subgroups this analysis is associated with.
        self.top_subgroups = []
        for group in subgroups.TopGroups:
            if group.id in self.subgroups:
                self.top_subgroups.append(group)
