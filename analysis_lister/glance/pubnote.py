"""Store information about PUB notes from glance.


"""

from attrs import define, field, validators
from enum import Enum, auto
import logging

from .glance_base import GlanceEntry

logger = logging.getLogger(__name__)


PUB_DATA_COLUMNS = {
    "Final URL": None,
    "Reference Code": None,
    "Short Title": None,
    "Status": None,
    "Subroups": None,
    "Superseded By": None,
    "Temporary Reference Code": None,
}


class PubNotePubState(Enum):
    """Enum for the publication state of a PUB note."""

    INACTIVE = auto()
    PUBLISHED = auto()
    ONGOING = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()


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
        """Initialise the PUB note instance through a dictionary.

        Takes a exported CSV file from GLANCE as input and generates (for one
        line of that CSV file) the corresponding instance of this class.

        Parameters:
            _dict: The dictionary with the info from the CSV file.

        Returns: Instantiated class object.

        """
        return cls(
            final_url=_dict["Final URL"],
            ref_code=_dict["Reference Code"],
            status=_dict["Status"],
            subgroups=_dict["Subroups"].split(","),
            superseded_by=_dict["Superseded By"],
            tmp_ref_code=_dict["Temporary Reference Code"],
            title_short=_dict["Short Title"],
            title_full=_dict["Short Title"],  # Reuse as placeholder
            title_short_public=_dict["Short Title"],  # Reuse as placeholder
            phase_state="",
            keywords=[],
        )

    def __attrs_post_init__(self):
        """Post-initialization processing for PUB note."""
        super().__attrs_post_init__()

        # Determine the publication state of the PUB note.
        if self.status == " Phase 1 is  Not started ":
            self.al_pub_state = PubNotePubState.INACTIVE
        elif self.superseded_by != "":
            self.al_pub_state = PubNotePubState.SUPERSEDED
        elif self.final_url != "":
            self.al_pub_state = PubNotePubState.PUBLISHED
        elif self.tmp_ref_code != self.ref_code:
            self.al_pub_state = PubNotePubState.ONGOING
        else:
            self.al_pub_state = PubNotePubState.UNKNOWN

        logger.debug("PUB note %s state: %s", self.ref_code, self.al_pub_state)
