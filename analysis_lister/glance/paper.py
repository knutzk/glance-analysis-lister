# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Store information about papers from glance.

The Paper class derives from the Analysis class and adds additional attributes
specific to analysis records published as papers. The class is instantiated
with a CSV file scraped from the GLANCE web interface. The list of required
fields is stored in .field_maps.REQUIRED_COLUMNS_PAPER.

Most attributes are direct translations of the column names in the CSV file,
others require more intricate parsing, handled in the post-init method.

"""

import logging

from attrs import define, field

from .. import citation_store
from ..citation_store import citation_text, normalize_doi
from ..diagnostics import lookup_notice, model_diagnostic
from .analysis import Analysis
from .doi import doi_from_url, order_doi_urls
from .enums import PublicationState
from .field_maps import FIELD_MAP_PAPER, apply_field_map
from .utils import get_init_fields, glance_paper_url

logger = logging.getLogger(__name__)


@define
class Paper(Analysis):
    """A class representing a published analysis with additional paper metadata.

    Attributes:
        arxiv_number: String with the arXiv number of the paper.
        arxiv_url: String with the arXiv URL of the paper.
        date_acceptance: String with the journal acceptance date.
        date_phase_one: String with the phase 1 start date.
        date_publication: String with the publication date.
        date_submission: String with the arXiv submission date.
        dois: List of DOIs of the paper, original publication first.
        doi_urls: List of DOI URLs of the paper, original publication first.
        figure_url: String with the figure URL of the paper.
        glance_url_publ: String with the glance URL of the paper.
        inspire_url: String with the inspire URL of the paper.
        journal: String with the journal of final submission.
        journal_ref: String with the journal reference of the paper.
        journal_ref_corrections: List of journal references of the erratum/
            addendum publications, aligned with dois[1:].
        status_paper: String with the status of the paper.
        title_final_tex: String with the final title in TeX format.

    A paper carries more than one DOI once an erratum or an addendum has been
    published, hence `dois` and `doi_urls` are lists. Their first entry is the
    original article, any further entry a later correction.

    """

    arxiv_number: str
    arxiv_url: str
    date_acceptance: str
    date_phase_one: str
    date_publication: str
    date_submission: str
    dois: list[str] = field(init=False)
    doi_urls: list[str]
    figure_url: str
    glance_url_publ: str = field(init=False)
    inspire_url: str
    journal: str
    journal_ref: str = field(init=False)
    journal_ref_corrections: list[str] = field(init=False)
    status_paper: str
    title_final_tex: str

    @classmethod
    def from_analysis_and_dict(cls, base: Analysis, _dict: dict[str, str]):
        """Create a Paper instance from an analysis and a dictionary.

        Args:
            base (Analysis): The base analysis instance.
            _dict (dict[str, str]): A dictionary containing the paper data.

        Returns:
            Paper: An instance of the Paper class.

        """
        paper_fields = apply_field_map(_dict, FIELD_MAP_PAPER)

        return cls(**get_init_fields(base, cls), **paper_fields)

    def determine_paper_status(self):
        """Determine the status of the paper.

        This method checks the status of the paper based on its attributes
        and updates the publication state of the instance accordingly.

        Returns:
            PublicationState: The publication state of the paper.

        """
        if self.status == " Phase 0 is  Not started ":
            return PublicationState.NOT_STARTED
        if self.status_paper == " Publication is  Closed ":
            return PublicationState.CLOSED
        if self.status_paper in (
            # A paper awaiting phase 1 is still an ongoing analysis.
            " Phase 1 is  Not started ",
            " Phase 1 is  Active ",
            " Phase 2 is  Active ",
        ) or (
            self.status_paper == " Publication Phase is  Active "
            and self.date_submission == ""
        ):
            return PublicationState.PHASE1_OR_2
        elif self.date_submission and not self.date_publication:
            return PublicationState.SUBMITTED_TO_JOURNAL
        elif self.date_publication:
            return PublicationState.PUBLISHED
        else:
            model_diagnostic(
                logger,
                logging.ERROR,
                "Paper %s has unknown publication state",
                self.ref_code,
            )
            return PublicationState.UNKNOWN

    def __attrs_post_init__(self):
        """Post-initialization of paper instance."""
        super().__attrs_post_init__()

        self.doi_urls = order_doi_urls(self.doi_urls, self.ref_code)
        self.dois = [doi_from_url(url) for url in self.doi_urls]
        self.glance_url_publ = glance_paper_url(self.ref_code)

        # Unstarted analyses stay excluded even with copied publication data.
        # Analysis and publication may also have been closed together.
        # Active phase-0 metadata can lag behind an attached paper. Keep it
        # visible in debug output; closed and unknown states remain warnings.
        closed_together = (
            self.pub_state == PublicationState.CLOSED
            and self.status_paper == " Publication is  Closed "
        )
        if (
            self.pub_state
            not in (
                PublicationState.PAST_PHASE0,
                PublicationState.NOT_STARTED,
            )
            and not closed_together
        ):
            level = (
                logging.DEBUG
                if self.pub_state
                in {
                    PublicationState.ONGOING_WO_EB,
                    PublicationState.ONGOING_WITH_EB,
                    PublicationState.PREAPPROVED,
                }
                else logging.WARNING
            )
            model_diagnostic(
                logger,
                level,
                "Paper %s has state '%s' while it should be '%s'",
                self.ref_code,
                self.pub_state,
                PublicationState.PAST_PHASE0,
            )

        self.pub_state = self.determine_paper_status()
        logger.debug("Paper %s state %s", self.ref_code, self.pub_state)

        # Every DOI gets its own journal reference: the original article, and
        # one per erratum/addendum. The corrections are kept apart from the
        # original so that they can be cited on a line of their own. An empty
        # string keeps them aligned with self.dois[1:].
        refs = []
        for index, doi in enumerate(self.dois):
            key = doi if doi in citation_store.Citations else normalize_doi(doi)
            if key in citation_store.Citations:
                value = citation_store.Citations[key]
                refs.append(citation_text(value))
            else:
                lookup_notice(
                    logger,
                    logging.WARNING,
                    "%s: no journal reference for %s DOI %s; add its citation "
                    "to the citation store using resolve-dois or edit json/doi_metadata.json",
                    self.ref_code,
                    "original article" if index == 0 else "correction",
                    doi,
                )
                refs.append("")

        if self.pub_state == PublicationState.SUBMITTED_TO_JOURNAL and self.journal:
            self.journal_ref = f"Submitted to {self.journal}"
        else:
            self.journal_ref = refs[0] if refs else ""

        self.journal_ref_corrections = refs[1:]
