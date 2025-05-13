"""Field maps for declarative parsing of GLANCE entry dictionaries.

"""

import re
from typing import Callable, Any

from . import utils


FIELD_MAP_ANALYSIS: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "ref_code": ("Reference Code", utils.format_ref_code),
    "title_short": ("Short Title", None),
    "title_full": ("Full Title", None),
    "title_short_public": ("Public Short Title", None),
    "status": ("Status", None),
    "phase_state": ("Phase State", None),
    "run": ("Run", None),
    "leading_group": ("Leading Group", None),
    "subgroups": ("Subgroups", lambda s: re.split(r",(?=\S)", s)),
    "contact_editors": ("Contact Editors", None),
    "int_note_editors": ("Internal Note Editors", None),
    "supporting_docs": ("Supporting Documents", utils.format_supporting_docs),
    "date_start": ("Phase 0 Start Date", None),
    "date_preapproval": ("Pre approval Meetings Dates", None),
    "date_preapproval_signoff": ("PGC or SGC sign-off date", None),
    "date_approval": ("Approval Meetings Dates", None),
    "date_eb_formed": ("Editorial Board Formed On", None),
    # special handling in code:
    # "contacts": ...
    # "editorial_board": ...
    "keywords": ("Keywords", lambda s: s.split(", ")),
}

FIELD_MAP_PAPER: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "ref_code": ("Reference Code", utils.format_ref_code),
    "title_short": ("Short Title", None),
    "title_full": ("Full Title", None),
    "title_short_public": ("Public Short Title", None),
    "status": ("Status", None),
    "phase_state": ("Phase State", None),
    "run": ("Run", None),
    "keywords": ("Keywords", lambda s: s.split(", ")),
    "subgroups": ("Subgroups", lambda s: s.split(",")),
    "contact_editors": ("Contact Editors", None),
    "date_phase_one": ("Phase 1 Start Date", None),
    "date_submission": ("arXiv Submission Date", None),
    "date_acceptance": ("Journal Acceptance Date", None),
    "date_publication": ("Publication Date", None),
    "arxiv_number": ("ArXiv Reference Number", None),
    "arxiv_url": ("ArXiv Reference URLs", None),
    "doi_url": ("Final Journal Publication URLs", utils.format_url_doi),
    "inspire_url": ("Final Journal Publication URLs", utils.format_url_inspire),
    "journal": ("Journal of Final Submission", None),
    "figure_url": ("Figures", None),
    "title_final_tex": ("Final Title (Tex)", None),
    # special handling in code:
    # "editorial_board": ...
}

FIELD_MAP_CONFNOTE: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "ref_code": ("Reference Code", None),
    "title_short": ("Short Title", None),
    "title_full": ("Short Title", None),
    "title_short_public": ("Short Title", None),
    "final_url": ("Final URL", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
    "superseded_by": ("Superseded By", None),
    "subgroups": ("Subroups", lambda s: s.split(",")),
    "status": ("", lambda _: ""),
    "phase_state": ("", lambda _: ""),
    "keywords": ("", lambda _: []),
}

FIELD_MAP_PUBNOTE: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "ref_code": ("Reference Code", None),
    "title_short": ("Short Title", None),
    "title_full": ("Short Title", None),
    "title_short_public": ("Short Title", None),
    "final_url": ("Final URL", None),
    "tmp_ref_code": ("Temporary Reference Code", None),
    "superseded_by": ("Superseded By", None),
    "status": ("Status", None),
    "subgroups": ("Subroups", lambda s: s.split(",")),
    "phase_state": ("", lambda _: ""),
    "keywords": ("", lambda _: []),
}
