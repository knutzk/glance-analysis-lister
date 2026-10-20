# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Store information about CONF notes from glance.

The ConfNote class derives from the Analysis class and adds additional
attributes specific to CONF notes. The class is instantiated with a CSV file
scraped from the GLANCE web interface. The list of required fields is stored
in .field_maps.REQUIRED_COLUMNS_CONFNOTE.

Most attributes are direct translations of the column names in the CSV file,
others require more intricate parsing, handled in the post-init method.

"""

import logging

from attrs import define

from ..diagnostics import model_diagnostic
from .analysis import Analysis
from .enums import PublicationState
from .field_maps import FIELD_MAP_CONFNOTE, apply_field_map
from .utils import get_init_fields, glance_confnote_url, has_note_number

logger = logging.getLogger(__name__)


@define
class ConfNote(Analysis):
    """A class representing a CONF note publication derived from an analysis.

    Attributes:
        date_signoff: The date the CONF note was signed off.
        final_ref_code: The CONF note number, e.g. "ATLAS-CONF-2022-058",
            as opposed to ref_code, which identifies the analysis.
        final_url: The final URL of the CONF note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the CONF note.

    """

    date_signoff: str
    final_ref_code: str
    final_url: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a CONF note instance from an analysis and a dictionary.

        Args:
            base (Analysis): The base analysis instance.
            _dict (dict[str, str]): A dictionary containing the CONF note data.

        Returns:
            ConfNote: An instance of the ConfNote class.

        """
        parsed = apply_field_map(_dict, FIELD_MAP_CONFNOTE)

        return cls(**get_init_fields(base, cls), **parsed)

    def determine_confnote_status(self):
        """Determine the status of the CONF note.

        This method checks the status of the CONF note based on its attributes
        and updates the publication state of the instance accordingly.

        Unlike PubNote, this has no INACTIVE case: the CSV of the CONF notes
        carries no status column of its own, and this method only runs for
        records whose analysis has finished phase 0.

        Returns:
            PublicationState: The publication state of the CONF note.

        """
        if self.superseded_by:
            return PublicationState.SUPERSEDED
        elif self.final_url:
            return PublicationState.PUBLISHED
        elif has_note_number(self.final_ref_code):
            # A note is only assigned a number of its own once it is out, so
            # a number without a URL is a gap in the GLANCE record rather
            # than a state of the note. Without the URL there is nothing to
            # link to, so it cannot be listed as published either.
            model_diagnostic(
                logger,
                logging.ERROR,
                "CONF note %s carries the number %s but no final URL, so it "
                "cannot be listed. Check the GLANCE record.",
                self.ref_code,
                self.final_ref_code.strip(),
            )
            return PublicationState.UNKNOWN
        else:
            return PublicationState.PHASE1_OR_2

    def __attrs_post_init__(self):
        """Post-initialization of CONF note instance."""
        super().__attrs_post_init__()

        # Preserve closed and unstarted analyses. Only finished phase 0
        # records are promoted to a note state; warn about other base states.
        if self.pub_state not in [
            PublicationState.PAST_PHASE0,
            PublicationState.CLOSED,
            PublicationState.NOT_STARTED,
        ]:
            model_diagnostic(
                logger,
                logging.WARNING,
                "CONF note %s has state '%s' while it should be '%s'",
                self.ref_code,
                self.pub_state,
                PublicationState.PAST_PHASE0,
            )

        if self.pub_state == PublicationState.PAST_PHASE0:
            self.pub_state = self.determine_confnote_status()

        logger.debug("CONF note %s state: %s", self.ref_code, self.pub_state)

        self.glance_url_publ = glance_confnote_url(self.ref_code)
