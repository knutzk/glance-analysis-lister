"""Store information about PUB notes from glance.


"""

from attrs import define
import logging

from .analysis import Analysis
from .enums import PublicationState
from .field_maps import FIELD_MAP_PUBNOTE
from .utils import get_init_fields

logger = logging.getLogger(__name__)


@define
class PubNote(Analysis):
    """A class representing a PUB note publication derived from an analysis.

    Attributes:
        final_url: The final URL of the PUB note.
        status_pub: The status of the PUB note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the PUB note.

    """

    final_url: str
    status_pub: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a PUB note instance from an analysis and a dictionary."""
        parsed = {}
        for key, (col, func) in FIELD_MAP_PUBNOTE.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **parsed)

    def __attrs_post_init__(self):
        """Post-initialization of PUB note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the PUB note. As this class
        # should only be instantiated for finished analysis records, issue
        # a warning if the publication state is not set to PAST_PHASE0.
        if self.pub_state != PublicationState.PAST_PHASE0:
            logger.warning(
                "PUB note %s has state '%s' while it should be '%s'",
                self.ref_code,
                self.pub_state,
                PublicationState.PAST_PHASE0,
            )

        self.pub_state = self.determine_pubnote_status()
        logger.debug("PUB note %s state: %s", self.ref_code, self.pub_state)

    def __str__(self):
        """Return a string representation of the PUB note instance."""
        return f"PUB note {self.ref_code} ({self.pub_state})"

    def determine_pubnote_status(self):
        """Determine the status of the PUB note."""
        if self.superseded_by:
            return PublicationState.SUPERSEDED
        elif self.final_url:
            return PublicationState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            return PublicationState.PHASE1_OR_2
        else:
            logger.error("PUB note %s has unknown publication state", self.ref_code)
            return PublicationState.UNKNOWN
