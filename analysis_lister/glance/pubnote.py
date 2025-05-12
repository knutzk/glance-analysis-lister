"""Store information about PUB notes from glance.


"""

from attrs import define, field, validators
from enum import Enum, auto
import logging

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
class PubNote:
    """A class to hold information about a glance PUB note entry.

    Attributes:
        al_pub_state: Enum for the publication state of the PUB note.
        final_url: String with the final URL of the PUB note.
        ref_code: String with the paper reference code.
        subgroups: String with the subgroups.
        superseded_by: String with the reference code of superseding entry.
        tmp_ref_code: String with the temporary reference code.
        title_short: String with the short title.

    """

    al_pub_state: PubNotePubState = field(
        validator=validators.instance_of(PubNotePubState), init=False
    )
    final_url: str
    ref_code: str
    status: str
    subgroups: str
    superseded_by: str
    tmp_ref_code: str
    title_short: str

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
        )

    def __attrs_post_init__(self):
        """Initialise those attributes derived from others."""

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

        logger.debug(f"PUB note {self.ref_code} state: {self.al_pub_state}")
