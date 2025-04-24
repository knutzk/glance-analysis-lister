"""Store information about PUB notes from glance.


"""

from attrs import define
import logging

logger = logging.getLogger(__name__)


PUB_DATA_COLUMNS = {
    "Final URL": None,
    "Reference Code": None,
    "Short Title": None,
    "Subroups": None,
    "Superseded By": None,
    "Temporary Reference Code": None,
}


@define
class PubNote:
    """A class to hold information about a glance PUB note entry.

    Attributes:
        is_published: Boolean indicating if the note is published.
        is_superseded: Boolean indicating if the note is superseded.
        ref_code: String with the paper reference code.
        subgroups: String with the subgroups.
        tmp_ref_code: String with the temporary reference code.
        title_short: String with the short title.

    """

    is_published: bool
    is_superseded: bool
    ref_code: str
    subgroups: str
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
            is_published=_dict["Final URL"] != "",
            is_superseded=_dict["Superseded By"] != "",
            ref_code=_dict["Reference Code"],
            subgroups=_dict["Subroups"].split(","),
            tmp_ref_code=_dict["Temporary Reference Code"],
            title_short=_dict["Short Title"],
        )

    def __attrs_post_init__(self):
        """Initialise those attributes derived from others."""
        pass
