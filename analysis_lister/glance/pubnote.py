from attrs import define, field, validators, fields
import logging

from .enums import PubNotePubState
from .analysis import Analysis
from .field_maps import FIELD_MAP_PUBNOTE

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
class PubNote(Analysis):
    """A class representing a PUB note publication derived from an analysis.

    Attributes:
        al_pub_state: Enum for the publication state of the PUB note.
        final_url: The final URL of the PUB note.
        status_pub: The status of the PUB note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the PUB note.

    """

    al_pub_state: PubNotePubState = field(
        validator=validators.instance_of(PubNotePubState), init=False
    )
    final_url: str
    status_pub: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        parsed = {}
        for key, (col, func) in FIELD_MAP_PUBNOTE.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **parsed)

    def __attrs_post_init__(self):
        """Post-initialization of PUB note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the PUB note.
        if self.status_pub == " Phase 1 is  Not started ":
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
