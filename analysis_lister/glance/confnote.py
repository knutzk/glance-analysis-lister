"""Store information about CONF notes from glance.


Extract table from GLANCE web UI. All columns listed in the
fields.CONF_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define
import logging

from .enums import PublicationState
from .analysis import Analysis
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

        # Determine the publication state of the CONF note.
        if self.superseded_by:
            self.pub_state = PublicationState.SUPERSEDED
        elif self.final_url:
            self.pub_state = PublicationState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            self.pub_state = PublicationState.PHASE1_OR_2
        else:
            self.pub_state = PublicationState.UNKNOWN

        logger.debug("CONF note %s state: %s", self.ref_code, self.pub_state)
