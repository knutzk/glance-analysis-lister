"""Store information about CONF notes from glance.


"""

from attrs import define, field, validators
from enum import Enum, auto
import logging

from .glance_base import GlanceEntry

logger = logging.getLogger(__name__)


CONF_DATA_COLUMNS = {
    "Final URL": None,
    "Reference Code": None,
    "Short Title": None,
    "Subroups": None,
    "Superseded By": None,
    "Temporary Reference Code": None,
}


class ConfNotePubState(Enum):
    """Enum for the publication state of a CONF note."""

    PUBLISHED = auto()
    ONGOING = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()


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
        """Initialise the CONF note instance through a dictionary.

        Takes a exported CSV file from GLANCE as input and generates (for one
        line of that CSV file) the corresponding instance of this class.

        Parameters:
            _dict: The dictionary with the info from the CSV file.

        Returns: Instantiated class object.

        """
        return cls(
            final_url=_dict["Final URL"],
            ref_code=_dict["Reference Code"],
            subgroups=_dict["Subroups"].split(","),
            superseded_by=_dict["Superseded By"],
            tmp_ref_code=_dict["Temporary Reference Code"],
            title_short=_dict["Short Title"],
            title_full=_dict["Short Title"],  # Reuse as placeholder
            title_short_public=_dict["Short Title"],  # Reuse as placeholder
            status="",
            phase_state="",
            keywords=[],
        )

    def __attrs_post_init__(self):
        """Post-initialization of CONF note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the CONF note.
        if self.superseded_by != "":
            self.al_pub_state = ConfNotePubState.SUPERSEDED
        elif self.final_url != "":
            self.al_pub_state = ConfNotePubState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            self.al_pub_state = ConfNotePubState.ONGOING
        else:
            self.al_pub_state = ConfNotePubState.UNKNOWN

        logger.debug("CONF note %s state: %s", self.ref_code, self.al_pub_state)
