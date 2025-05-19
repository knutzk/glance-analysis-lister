"""Glance registry module.


This module provides the GlanceRegistry class, which is responsible for
loading and enriching ATLAS analysis records from CSV files. It provides
programmatic access to the complete and filtered sets of analyses,
papers, CONF notes, and PUB notes. The class supports filtering by
publication state and type, and includes utilities to determine file
modification timestamps.

"""

import csv
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Union

from .analysis import Analysis
from .confnote import ConfNote
from .paper import Paper
from .pubnote import PubNote
from .enums import PublicationState

logger = logging.getLogger(__name__)


class _FilteringMixin:
    """Mixin class to provide filtering and counting methods for analyses."""

    def count(self, predicate: Callable[[Analysis], bool]) -> int:
        """Count entries matching a custom filter predicate."""
        return len(self.filter(predicate))

    def count_by_state(
        self, predicate: Callable[[Analysis], bool]
    ) -> dict[PublicationState, int]:
        """Count entries matching a custom filter predicate grouped by publication state."""
        counts = {state: 0 for state in PublicationState}
        for entry in self._analyses.values():
            if predicate(entry):
                counts[entry.pub_state] += 1
        return counts

    def filter(self, predicate: Callable[[Analysis], bool]) -> list[Analysis]:
        """Filter analyses based on a custom predicate function."""
        return [a for a in self._analyses.values() if predicate(a)]


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
        logger.info("Initializing GlanceRegistry...")
        self.analysis_path = Path(csv_dir) / analysis_csv
        self.paper_path = Path(csv_dir) / paper_csv
        self.confnote_path = Path(csv_dir) / confnote_csv
        self.pubnote_path = Path(csv_dir) / pubnote_csv
        self.threshold_year = threshold_year
        self._analyses: dict[str, Analysis] = {}

        self._load_and_enrich()

    def __repr__(self):
        return f"<GlanceRegistry: {len(self._analyses)} analyses>"

    def __str__(self):
        summary = f"GlanceRegistry: "
        summary += f"{len(self.analyses)} ongoing analyses, "
        summary += f"{len(self.papers)} submitted/published papers, "
        summary += f"{len(self.confnotes)} CONF notes, "
        summary += f"{len(self.pubnotes)} PUB notes"
        return summary

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

    def store_json(self, path: Path):
        """Store the registry as a JSON file with serialized entries."""
        import json
        from attrs import asdict
        from enum import Enum

        def serializer(instance, field, value):
            if isinstance(value, Enum):
                return value.value
            return value

        serializable_registry = {
            ref_code: asdict(entry, value_serializer=serializer)
            for ref_code, entry in self._analyses.items()
        }

        with open(path, "w", encoding="utf8") as f:
            json.dump(serializable_registry, f, indent=4, ensure_ascii=False)

        logger.info("Stored registry as JSON file at %s", path)

    # --- Public Properties: Access to Data ---

    @property
    def analyses(self) -> list[Union[Analysis, Paper, ConfNote, PubNote]]:
        """All analyses that are ongoing/under review.

        Some of these entries may have been promoted to papers or notes, but
        if they are still in the review process, they are included here.

        """
        return self.filter(lambda a: a.is_ongoing())

    @property
    def confnotes(self) -> list[ConfNote]:
        """All entries that should be listed as CONF note."""
        return self.filter(
            lambda a: isinstance(a, ConfNote)
            and a.pub_state == PublicationState.PUBLISHED
        )

    @property
    def entries(self) -> dict[str, Union[Analysis, Paper, ConfNote, PubNote]]:
        """Direct access to the internal registry dictionary."""
        return self._analyses.copy()

    @property
    def papers(self) -> list[Paper]:
        """All entries that should be listed as paper.

        This includes all papers that are either in SUBMITTED_TO_JOURNAL state
        or PUBLISHED with a publication date greater than the threshold year.

        """
        return self.filter(
            lambda a: isinstance(a, Paper)
            and (
                a.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
                or (
                    a.pub_state == PublicationState.PUBLISHED
                    and a.date_publication >= self.threshold_year
                )
            )
        )

    @property
    def pubnotes(self) -> list[PubNote]:
        """All entries that should be listed as PUB note."""
        return self.filter(
            lambda a: isinstance(a, PubNote)
            and a.pub_state == PublicationState.PUBLISHED
        )

    # --- Internal Load and Enrich ---

    def _enrich(self, path: Path, cls, key: str, prefix: str = ""):
        n_enriched = 0
        for row in self._read_csv_rows(path):
            ref = row[key].removeprefix(prefix)
            if ref in self._analyses:
                base = self._analyses[ref]
                self._analyses[ref] = cls.from_analysis_and_dict(base, row)
                n_enriched += 1

    def _load_and_enrich(self):
        # Load the analysis database from the CSV file.
        logger.info("Loading list of analyses from file %s", self.analysis_path.name)
        self._analyses = {
            a.ref_code: a for a in self._load_data(self.analysis_path, Analysis)
        }
        logger.info("Loaded %d analysis base entries.", len(self._analyses))

        # Load papers from the CSV file and enrich corresponding analysis entries.
        logger.info("Loading list of papers from file %s", self.paper_path.name)
        self._enrich(self.paper_path, Paper, key="Reference Code")
        logger.info("Enriched %d analyses with paper data.", len(self.papers))

        # Load CONF notes from the CSV files and enrich corresponding analysis entries.
        logger.info("Loading list of CONF notes from file %s", self.confnote_path.name)
        self._enrich(
            self.confnote_path, ConfNote, key="Temporary Reference Code", prefix="CONF-"
        )
        logger.info("Enriched %d analyses with CONF note data.", len(self.confnotes))

        # Load PUB notes from the CSV files and enrich corresponding analysis entries.
        logger.info("Loading list of PUB notes from file %s", self.pubnote_path.name)
        self._enrich(
            self.pubnote_path, PubNote, key="Temporary Reference Code", prefix="PUB-"
        )
        logger.info("Enriched %d analyses with PUB note data.", len(self.pubnotes))

    def _load_data(self, path: Path, cls):
        rows = self._read_csv_rows(path)
        data = [cls.from_dict(row) for row in rows]
        return sorted(data, key=lambda x: x.ref_code)

    def _read_csv_rows(self, path: Path):
        try:
            with open(path, encoding="utf8") as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            logger.warning(f"File {path} not found.")
            return []
