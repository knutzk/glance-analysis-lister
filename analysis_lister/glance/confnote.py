"""Store information about CONF notes from glance.


Extract table from GLANCE web UI. All columns listed in the
fields.CONF_DATA_COLUMNS dictionary are required inputs.

"""

from attrs import define, field, fields, validators
import logging

from .enums import ConfNotePubState
from .analysis import Analysis

logger = logging.getLogger(__name__)


def get_init_fields(source_obj, target_cls):
    """Return fields from source_obj that are init=True in target_cls."""
    target_init_fields = {f.name for f in fields(target_cls) if f.init}
    return {
        name: getattr(source_obj, name)
        for name in target_init_fields
        if hasattr(source_obj, name)
    }


@define
class ConfNote(Analysis):
    """A class representing a CONF note publication derived from an analysis.

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
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        parsed = {}
        for key, (col, func) in FIELD_MAP_CONF.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **parsed)

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
