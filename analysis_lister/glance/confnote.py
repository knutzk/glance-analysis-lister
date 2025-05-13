"""Store information about CONF notes from glance.


The ConfNote class derives from the Analysis class and adds additional
attributes specific to CONF notes. The class is instantiated with a CSV file
scraped from the GLANCE web interface. The list of required fields is stored
in .field_maps.REQUIRED_COLUMNS_CONFNOTE.

Most attributes are direct translations of the column names in the CSV file,
others require more intricate parsing, handled in the post-init method.

"""

from attrs import define
import logging

from .analysis import Analysis
from .enums import PublicationState
from .field_maps import FIELD_MAP_CONFNOTE
from .utils import get_init_fields

logger = logging.getLogger(__name__)


@define
class ConfNote(Analysis):
    """A class representing a CONF note publication derived from an analysis.

    Attributes:
        final_url: The final URL of the CONF note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the CONF note.

    """

    final_url: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a CONF note instance from an analysis and a dictionary."""
        parsed = {}
        for key, (col, func) in FIELD_MAP_CONFNOTE.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **parsed)

    def __attrs_post_init__(self):
        """Post-initialization of CONF note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the CONF note. As this class
        # should only be instantiated for finished analysis records, issue
        # a warning if the publication state is not set to PAST_PHASE0.
        if self.pub_state not in [
            PublicationState.PAST_PHASE0,
            PublicationState.CLOSED]:
            logger.warning(
                "CONF note %s has state '%s' while it should be '%s'",
                self.ref_code,
                self.pub_state,
                PublicationState.PAST_PHASE0,
            )

        if self.pub_state == PublicationState.PAST_PHASE0:
            self.pub_state = self.determine_confnote_status()
        logger.debug("CONF note %s state: %s", self.ref_code, self.pub_state)

    def determine_confnote_status(self):
        """Determine the status of the CONF note."""
        if self.status == " Phase 1 is  Not started ":
            return PublicationState.INACTIVE
        elif self.superseded_by:
            return PublicationState.SUPERSEDED
        elif self.final_url:
            return PublicationState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            return PublicationState.PHASE1_OR_2
        else:
            logger.error("CONF note %s has unknown publication state", self.ref_code)
            return PublicationState.UNKNOWN
