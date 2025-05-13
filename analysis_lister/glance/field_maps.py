"""Declarative field maps for GLANCE CSV entry parsing.


Each FIELD_MAP_* dictionary maps class attribute names to a 2-tuple:
    (CSV column name, transformation function)

  - The CSV column name is the key expected in a row of the input CSV.
  - The transformation function takes the raw string value from the CSV and
    returns a cleaned or converted value. If no transformation is needed, use
    `None`.

This structure allows each class (Analysis, Paper, etc.) to define its
`from_dict()` logic in a generic and consistent way.

Fields that require information from multiple CSV columns (e.g., 'contacts' or
'editorial_board') are handled separately.

Example:
    FIELD_MAP_ANALYSIS = {
        "ref_code": ("Reference Code", utils.format_ref_code),
        "keywords": ("Keywords", lambda s: s.split(", ")),
        "title_short": ("Short Title", None),
    }

"""

import re
from typing import Callable, Any

from . import utils


FIELD_MAP_ANALYSIS: dict[str, tuple[str, Callable[[str], Any] | None]] = {
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

FIELD_MAP_PAPER: dict[str, tuple[str, Callable[[str], Any] | None]] = {
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

FIELD_MAP_CONFNOTE: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "final_url": ("Final URL", None),
    "superseded_by": ("Superseded By", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
}

FIELD_MAP_PUBNOTE: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "final_url": ("Final URL", None),
    "status_pub": ("Status", None),
    "superseded_by": ("Superseded By", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
}
