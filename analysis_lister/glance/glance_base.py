from attrs import define, field
from typing import List
import logging

from . import subgroups, utils

logger = logging.getLogger(__name__)


@define
class GlanceEntry:
    ref_code: str
    title_full: str
    title_short: str
    title_short_public: str
    subgroups: List[str]
    status: str
    phase_state: str
    keywords: List[str]

    glance_url_analysis: str = field(init=False)
    top_subgroups: List[str] = field(init=False)

    def __attrs_post_init__(self):
        self.glance_url_analysis = utils.glance_analysis_url(self.ref_code)

        self.title_full, self.title_short, self.title_short_public = utils.clean_titles(
            self.title_full, self.title_short, self.title_short_public
        )

        self.top_subgroups = utils.get_top_subgroups(
            self.subgroups, subgroups.TopGroups
        )

        logger.debug("Initialized GlanceEntry for %s", self.ref_code)
