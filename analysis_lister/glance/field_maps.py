"""Declarative field maps for GLANCE CSV entry parsing.


Each FIELD_MAP_* dictionary maps class attribute names to a 2-tuple:
    (CSV column name, transformation function)

  - The CSV column name is the key expected in a row of the input CSV.
  - The transformation function takes the raw string value from the CSV and
    returns a cleaned or converted value. If no transformation is needed, use
    `None`.

This structure allows each class (Analysis, Paper, etc.) to define its
`from_dict()` logic in a generic and consistent way. Fields that require
information from multiple CSV columns (e.g., 'contacts' or
'editorial_board') are handled separately.

EXTRA_COLUMNS_* lists are used to add additional fields that are not
initialised in the constructor but are required for the class to function
correctly. These fields are typically derived from the CSV data but are not
directly represented in the CSV file.

The `REQUIRED_COLUMNS_*` lists are used to validate the presence of
required fields in the CSV file. They are constructed by combining the
fields from the `FIELD_MAP_*` dictionaries and the `EXTRA_COLUMNS_*` lists.

"""

import re
from typing import Callable, Any, Union

from . import utils


FIELD_MAP_ANALYSIS: dict[str, tuple[str, Union[Callable[[str], Any], None]]] = {
    # "contacts" needs special handling
    "contact_editors": ("Contact Editors", None),
    "date_approval": ("Approval Meetings Dates", None),
    "date_eb_formed": ("Editorial Board Formed On", None),
    "date_preapproval_signoff": ("PGC or SGC sign-off date", None),
    "date_preapproval": ("Pre approval Meetings Dates", None),
    "date_start": ("Phase 0 Start Date", None),
    # "editorial_board" needs special handling
    "int_note_editors": ("Internal Note Editors", None),
    "keywords": ("Keywords", lambda s: s.split(", ")),
    "leading_group": ("Leading Group", None),
    "phase_state": ("Phase State", None),
    "ref_code": ("Reference Code", utils.format_ref_code),
    "run": ("Run", None),
    "status": ("Status", None),
    "subgroups": ("Subgroups", lambda s: re.split(r",(?=\S)", s)),
    "supporting_docs": ("Supporting Documents", utils.format_supporting_docs),
    "title_full": ("Full Title", None),
    "title_short_public": ("Public Short Title", None),
    "title_short": ("Short Title", None),
}

# Not initialised in the constructor, but in the post-init method.
EXTRA_COLUMNS_ANALYSIS = [
    "Analysis Contacts",
    "Analysis Contacts' Start Date",
    "Analysis Contacts' End Date",
    "Editorial Board",
    "Chairs",
]

# Required columns in the analysis CSV file.
REQUIRED_COLUMNS_ANALYSIS = [
    *(col for col, _ in FIELD_MAP_ANALYSIS.values()),
    *EXTRA_COLUMNS_ANALYSIS,
]

FIELD_MAP_PAPER: dict[str, tuple[str, Union[Callable[[str], Any], None]]] = {
    "arxiv_number": ("ArXiv Reference Number", None),
    "arxiv_url": ("ArXiv Reference URLs", None),
    "date_acceptance": ("Journal Acceptance Date", None),
    "date_phase_one": ("Phase 1 Start Date", None),
    "date_publication": ("Publication Date", None),
    "date_submission": ("arXiv Submission Date", None),
    "doi_url": ("Final Journal Publication URLs", utils.format_url_doi),
    "figure_url": ("Figures", None),
    "inspire_url": ("Final Journal Publication URLs", utils.format_url_inspire),
    "journal": ("Journal of Final Submission", None),
    "status_paper": ("Status", None),
    "title_final_tex": ("Final Title (Tex)", None),
}

# Not initialised in the constructor, but in the post-init method.
EXTRA_COLUMNS_PAPER = [
    "Chairs",
    "Contact Editors",
    "Current Paper Draft",
    "Editorial Board",
    "Full Title",
    "Keywords",
    "Leading Group",
    "Phase State",
    "Public Short Title",
    "Reference Code",
    "Run",
    "Short Title",
    "Status",
    "Subgroups",
    "Supporting Documents",
]

# Required columns in the paper CSV file.
REQUIRED_COLUMNS_PAPER = [
    *(col for col, _ in FIELD_MAP_PAPER.values()),
    *EXTRA_COLUMNS_PAPER,
]

FIELD_MAP_CONFNOTE: dict[str, tuple[str, Union[Callable[[str], Any], None]]] = {
    "date_signoff": ("Second Sign Off Date", None),
    "final_url": ("Final URL", None),
    "superseded_by": ("Superseded By", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
}

# Not initialised in the constructor, but in the post-init method.
EXTRA_COLUMNS_CONFNOTE = ["Reference Code"]

# Required columns in the confnote CSV file.
REQUIRED_COLUMNS_CONFNOTE = [
    *(col for col, _ in FIELD_MAP_CONFNOTE.values()),
    *EXTRA_COLUMNS_CONFNOTE,
]

FIELD_MAP_PUBNOTE: dict[str, tuple[str, Union[Callable[[str], Any], None]]] = {
    "final_url": ("Final URL", None),
    "status_pub": ("Status", None),
    "superseded_by": ("Superseded By", None),
    "date_signoff": ("Second Reader Sign Off Date", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
}

# Not initialised in the constructor, but in the post-init method.
EXTRA_COLUMNS_PUBNOTE = ["Reference Code"]

# Required columns in the pubnote CSV file.
REQUIRED_COLUMNS_PUBNOTE = [
    *(col for col, _ in FIELD_MAP_PUBNOTE.values()),
    *EXTRA_COLUMNS_PUBNOTE,
]
