from attrs import define, field, validators
import logging

from .glance_base import GlanceEntry
from .enums import PubNotePubState
from .field_maps import FIELD_MAP_PUBNOTE

logger = logging.getLogger(__name__)


@define
class PubNote(GlanceEntry):
    """A class to hold information about a glance PUB note entry.

    Attributes:
        al_pub_state: Enum for the publication state of the PUB note.
        final_url: The final URL of the PUB note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the PUB note.

    """

    al_pub_state: PubNotePubState = field(
        validator=validators.instance_of(PubNotePubState), init=False
    )
    final_url: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_dict(cls, _dict):
        """Initialise the PUB note instance through a dictionary."""
        parsed = {
            key: (
                func(_dict[col])
                if col and func
                else (_dict.get(col, "") if col else func(""))
            )
            for key, (col, func) in FIELD_MAP_PUBNOTE.items()
        }
        return cls(**parsed)

    def __attrs_post_init__(self):
        """Post-initialization of PUB note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the PUB note.
        if self.status == " Phase 1 is  Not started ":
            self.al_pub_state = PubNotePubState.INACTIVE
        elif self.superseded_by:
            self.al_pub_state = PubNotePubState.SUPERSEDED
        elif self.final_url:
            self.al_pub_state = PubNotePubState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            self.al_pub_state = PubNotePubState.ONGOING
        else:
            self.al_pub_state = PubNotePubState.UNKNOWN

        logger.debug("PUB note %s state: %s", self.ref_code, self.al_pub_state)
