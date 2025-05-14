import csv
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Union

from .analysis import Analysis
from .confnote import ConfNote
from .paper import Paper
from .pubnote import PubNote
from .enums import PublicationState

logger = logging.getLogger(__name__)


class _FilteringMixin:
    def _filter_by_type(self, cls) -> list:
        return [a for a in self._analyses.values() if isinstance(a, cls)]

    def _filter_by_type_and_state(self, cls, states: set[PublicationState]) -> list:
        return [
            a
            for a in self._analyses.values()
            if isinstance(a, cls) and a.pub_state in states
        ]


class GlanceRegistry(_FilteringMixin):
    """A class to manage and enrich analyses from CSV files.

    This class loads and enriches ATLAS analysis records, and provides
    programmatic access to the complete and filtered sets of:
      - analyses
      - papers
      - CONF notes
      - PUB notes

    It supports filtering by publication state and type, and includes
    utilities to determine file modification timestamps.
    """

    def __init__(
        self,
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        csv_dir="csv",
        threshold_year="2020",
    ):
        self.analysis_path = Path(csv_dir) / analysis_csv
        self.paper_path = Path(csv_dir) / paper_csv
        self.confnote_path = Path(csv_dir) / confnote_csv
        self.pubnote_path = Path(csv_dir) / pubnote_csv
        self.threshold_year = threshold_year
        self._analyses: dict[str, Analysis] = {}

        self._load_and_enrich()

    def __repr__(self):
        return f"<GlanceRegistry: {len(self._analyses)} analyses>"

    # --- Public API Methods ---

    def get(self, ref_code: str) -> Analysis | None:
        """Get an analysis by its reference code."""
        return self._analyses.get(ref_code)

    def determine_last_modified_time(self) -> str:
        """Return the latest modification timestamp for CSV files as string."""
        max_timestamp = 0
        for path in [self.analysis_path, self.paper_path]:
            try:
                ts = path.stat().st_mtime
                max_timestamp = max(max_timestamp, ts)
            except FileNotFoundError:
                continue

        last_modified = datetime.fromtimestamp(
            max_timestamp, tz=ZoneInfo("Europe/Zurich")
        )
        return last_modified.strftime("%b %d, %Y, %H:%M (%Z)")

    # --- Public Properties: Access to Data ---

    @property
    def analyses(self) -> list[Analysis]:
        """All analyses, including enriched entries (papers/notes)."""
        return list(self._analyses.values())

    @property
    def analyses_filtered(self) -> list[Analysis]:
        """Analyses in an ongoing or review state."""
        return self._filter_by_type_and_state(
            Analysis,
            {
                PublicationState.ONGOING_WITH_EB,
                PublicationState.ONGOING_WO_EB,
                PublicationState.PREAPPROVED,
                PublicationState.PHASE1_OR_2,
            },
        )

    @property
    def confnotes(self) -> list[ConfNote]:
        """All entries promoted to CONF note."""
        return self._filter_by_type(ConfNote)

    @property
    def confnotes_filtered(self) -> list[ConfNote]:
        """CONF notes in published state."""
        return self._filter_by_type_and_state(ConfNote, {PublicationState.PUBLISHED})

    @property
    def entries(self) -> dict[str, GlanceEntry]:
        """Direct access to the internal registry dictionary."""
        return self._analyses.copy()

    @property
    def pubnotes(self) -> list[PubNote]:
        """All entries promoted to PUB note."""
        return self._filter_by_type(PubNote)

    @property
    def pubnotes_filtered(self) -> list[PubNote]:
        """PUB notes in published state."""
        return self._filter_by_type_and_state(PubNote, {PublicationState.PUBLISHED})

    @property
    def papers(self) -> list[Paper]:
        """All entries promoted to Paper."""
        return self._filter_by_type(Paper)

    @property
    def papers_filtered(self) -> list[Paper]:
        """Submitted or recently published papers (since threshold year)."""
        return [
            a
            for a in self._filter_by_type(Paper)
            if a.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
            or (
                a.pub_state == PublicationState.PUBLISHED
                and a.date_publication >= self.threshold_year
            )
        ]

    # --- Internal Load and Enrich ---

    def _enrich(self, path: Path, cls, key: str, prefix: str = ""):
        for row in self._read_csv_rows(path):
            ref = row[key].removeprefix(prefix)
            if ref in self._analyses:
                base = self._analyses[ref]
                self._analyses[ref] = cls.from_analysis_and_dict(base, row)

    def _load_and_enrich(self):
        self._analyses = {
            a.ref_code: a for a in self._load_data(self.analysis_path, Analysis)
        }
        self._enrich(self.paper_path, Paper, key="Reference Code")
        self._enrich(
            self.confnote_path, ConfNote, key="Temporary Reference Code", prefix="CONF-"
        )
        self._enrich(
            self.pubnote_path, PubNote, key="Temporary Reference Code", prefix="PUB-"
        )

    def _load_data(self, path: Path, cls):
        rows = self._read_csv_rows(path)
        data = [cls.from_dict(row) for row in rows]
        logger.info(f"Loaded {len(data)} items from {path.name}.")
        return sorted(data, key=lambda x: x.ref_code)

    def _read_csv_rows(self, path: Path):
        try:
            with open(path, encoding="utf8") as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            logger.warning(f"File {path} not found.")
            return []
