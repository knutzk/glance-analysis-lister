"""Store information about PUB notes from glance.


The PubNote class derives from the Analysis class and adds additional
attributes specific to PUB notes. The class is instantiated with a CSV file
scraped from the GLANCE web interface. The list of required fields is stored
in .field_maps.REQUIRED_COLUMNS_PUBNOTE.

Most attributes are direct translations of the column names in the CSV file,
others require more intricate parsing, handled in the post-init method.

"""

from attrs import define
import logging

from .analysis import Analysis
from .enums import PublicationState
from .field_maps import FIELD_MAP_PUBNOTE
from .utils import get_init_fields, glance_pubnote_url, has_note_number

logger = logging.getLogger(__name__)


@define
class PubNote(Analysis):
    """A class representing a PUB note publication derived from an analysis.

    Attributes:
        date_signoff: The date the PUB note was signed off.
        final_ref_code: The PUB note number, e.g. "ATL-PHYS-PUB-2015-010",
            as opposed to ref_code, which identifies the analysis.
        final_url: The final URL of the PUB note.
        status_pub: The status of the PUB note.
        superseded_by: The reference code of the note that supersedes this one.
        tmp_ref_code: The temporary reference code of the PUB note.

    """

    date_signoff: str
    final_ref_code: str
    final_url: str
    status_pub: str
    superseded_by: str
    tmp_ref_code: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a PUB note instance from an analysis and a dictionary.

        Args:
            base (Analysis): The base analysis instance.
            _dict (dict[str, str]): A dictionary containing the PUB note data.

        Returns:
            PubNote: An instance of the PubNote class.

        """
        parsed = {}
        for key, (col, func) in FIELD_MAP_PUBNOTE.items():
            raw = _dict.get(col, "") if col else ""
            parsed[key] = func(raw) if func else raw

        return cls(**get_init_fields(base, cls), **parsed)

    def determine_pubnote_status(self):
        """Determine the status of the PUB note.

        This method checks the status of the PUB note and returns the
        corresponding publication state of the instance accordingly.

        Returns:
            PublicationState: The publication state of the PUB note.

        """
        if self.status_pub == " Phase 1 is  Not started ":
            return PublicationState.INACTIVE
        elif self.superseded_by:
            return PublicationState.SUPERSEDED
        elif self.final_url:
            return PublicationState.PUBLISHED
        elif has_note_number(self.final_ref_code):
            # A note is only assigned a number of its own once it is out, so
            # a number without a URL is a gap in the GLANCE record rather
            # than a state of the note. Without the URL there is nothing to
            # link to, so it cannot be listed as published either.
            logger.error(
                "PUB note %s carries the number %s but no final URL, so it "
                "cannot be listed. Check the GLANCE record.",
                self.ref_code,
                self.final_ref_code.strip(),
            )
            return PublicationState.UNKNOWN
        else:
            return PublicationState.PHASE1_OR_2

    def __attrs_post_init__(self):
        """Post-initialization of PUB note instance."""
        super().__attrs_post_init__()

        # Determine the publication state of the PUB note. As this class
        # should only be instantiated for finished analysis records, issue
        # a warning if the publication state is not set to PAST_PHASE0.
        if self.pub_state not in [
            PublicationState.PAST_PHASE0,
            PublicationState.CLOSED,
        ]:
            logger.warning(
                "PUB note %s has state '%s' while it should be '%s'",
                self.ref_code,
                self.pub_state,
                PublicationState.PAST_PHASE0,
            )

        if self.pub_state == PublicationState.PAST_PHASE0:
            self.pub_state = self.determine_pubnote_status()

        logger.debug("PUB note %s state: %s", self.ref_code, self.pub_state)

        # Set the glance URL for the PUB note.
        self.glance_url_publ = glance_pubnote_url(self.ref_code)
