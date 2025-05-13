"""Store information about CONF notes from glance.


Extract table from GLANCE web UI. All columns listed in the
fields.CONF_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, validators
import logging

from .glance_base import GlanceEntry
from .enums import ConfNotePubState
from .field_maps import FIELD_MAP_CONFNOTE

logger = logging.getLogger(__name__)


@define
class ConfNote(GlanceEntry):
    """A class to hold information about a glance CONF note entry.

    Attributes:
        al_pub_state: Enum for the publication state of the CONF note.
        final_url: The final URL of the CONF note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the CONF note.

    """

    al_pub_state: ConfNotePubState = field(
        validator=validators.instance_of(ConfNotePubState), init=False
    )
    final_url: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_dict(cls, _dict):
        """Initialise the CONF note instance through a dictionary."""
        parsed = {
            key: (
                func(_dict[col])
                if col and func
                else (_dict.get(col, "") if col else func(""))
            )
            for key, (col, func) in FIELD_MAP_CONFNOTE.items()
        }
        return cls(**parsed)

    def __attrs_post_init__(self):
        """Post-initialization of CONF note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the CONF note.
        if self.superseded_by:
            self.al_pub_state = ConfNotePubState.SUPERSEDED
        elif self.final_url:
            self.al_pub_state = ConfNotePubState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            self.al_pub_state = ConfNotePubState.ONGOING
        else:
            self.al_pub_state = ConfNotePubState.UNKNOWN

        logger.debug("CONF note %s state: %s", self.ref_code, self.al_pub_state)
