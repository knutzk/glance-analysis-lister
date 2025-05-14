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

GlanceEntry = Union[Analysis, Paper, ConfNote, PubNote]


class GlanceRegistry:
    """A class to manage and enrich analyses from CSV files.

    This class is responsible for loading analyses from CSV files, enriching
    them with additional information, and providing methods to access the
    analyses. It supports filtering analyses based on their type and
    publication state. The class also provides a method to determine the
    last modified time of the analysis and paper CSV files.

    Attributes:
        analysis_path: Path to the analysis CSV file.
        paper_path: Path to the paper CSV file.
        confnote_path: Path to the CONF note CSV file.
        pubnote_path: Path to the PUB note CSV file.
        threshold_year: Year used for filtering papers.
        _analyses: Dictionary of analyses indexed by their reference code.

    Public Methods:
        get: Get an analysis by its reference code.
        determine_last_modified_time: Determine the last modified time of the
            analysis and paper CSV files.

    Properties:
        analyses: Get all analyses (no filtering).
        analyses_filtered: Get a list of all ongoing analyses.
        papers: Get all papers (no filtering).
        papers_filtered: Get all submitted and published papers (≥ threshold year).
        confnotes: Get all CONF notes (no filtering).
        confnotes_filtered: Get all published CONF notes.
        pubnotes: Get all PUB notes (no filtering).
        pubnotes_filtered: Get all published PUB notes.

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

    def _load_and_enrich(self):
        """Load and enrich analyses from CSV files.

        This method is the central part of the class, responsible for loading
        data from the CSV files and enriching the analyses with additional
        information. It first loads the analyses from the analysis CSV file,
        then enriches them with data from the paper, CONF note, and PUB note
        CSV files. The enrichment is done by looking up the reference code
        in the analyses dictionary and updating the corresponding analysis
        object with the data from the CSV file.

        """
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
        """Load data from a CSV file and return a list of instances of the given class.

        This method reads the CSV file, creates instances of the specified class
        for each row, and returns a sorted list of these instances. The sorting
        is done based on the reference code of the instances.

        Args:
            path: Path to the CSV file.
            cls: Class to instantiate for each row.

        Returns:
            list[cls]: A sorted list of instances of the specified class.

        """
        rows = self._read_csv_rows(path)
        data = [cls.from_dict(row) for row in rows]
        logger.info(f"Loaded {len(data)} items from {path.name}.")
        return sorted(data, key=lambda x: x.ref_code)

    def _read_csv_rows(self, path: Path):
        """Read rows from a CSV file and return them as a list of dictionaries.

        This method uses the csv.DictReader to read the CSV file and convert
        each row into a dictionary. The keys of the dictionary are the column
        names from the first row of the CSV file. If the file is not found,
        a warning is logged and an empty list is returned.

        Args:
            path: Path to the CSV file.

        Returns:
            list[dict]: A list of dictionaries of the rows in the CSV file.

        """
        try:
            with open(path, encoding="utf8") as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            logger.warning(f"File {path} not found.")
            return []

    def _enrich(self, path: Path, cls, key: str, prefix: str = ""):
        """Enrich the analyses with additional data from a CSV file.

        This method reads the CSV file, looks up the reference code in the
        analyses dictionary, and updates the corresponding analysis object
        with the data from the CSV file. The reference code in the CSV file
        is expected to be prefixed with the specified prefix (e.g., "CONF-"
        or "PUB-"). The method will remove the prefix before looking up the
        analysis object in the dictionary.

        Args:
            path: Path to the CSV file.
            cls: Class to instantiate for each row.
            key: Key to look up in the CSV file.
            prefix: Prefix to remove from the key value.

        """
        for row in self._read_csv_rows(path):
            ref = row[key].removeprefix(prefix)
            if ref in self._analyses:
                base = self._analyses[ref]
                self._analyses[ref] = cls.from_analysis_and_dict(base, row)

    def get(self, ref_code: str) -> Analysis | None:
        """Get an analysis by its reference code.

        This method looks up the reference code in the analyses dictionary
        and returns the corresponding analysis object. If the reference code
        is not found, None is returned.

        Args:
            ref_code: Reference code of the analysis.

        Returns:
            Analysis | None: The analysis object if found, otherwise None.

        """
        return self._analyses.get(ref_code)

    @property
    def analyses(self) -> list[Analysis]:
        """Get all analyses (no filtering)."""
        return list(self._analyses.values())

    @property
    def analyses_filtered(self) -> list[Analysis]:
        """Get a list of all ongoing analyses."""
        states = {
            PublicationState.ONGOING_WITH_EB,
            PublicationState.ONGOING_WO_EB,
            PublicationState.PREAPPROVED,
            PublicationState.PHASE1_OR_2,
        }
        return [a for a in self._analyses.values() if a.pub_state in states]

    def _filter_by_type_and_state(self, cls, states: set[PublicationState]) -> list:
        """Filter analyses by type and publication state."""
        return [
            a
            for a in self._analyses.values()
            if isinstance(a, cls) and a.pub_state in states
        ]

    @property
    def papers(self) -> list[Paper]:
        """Get all papers (no filtering)."""
        return [a for a in self._analyses.values() if isinstance(a, Paper)]

    @property
    def papers_filtered(self) -> list[Paper]:
        """Get all submitted and published papers (≥ threshold year)."""
        return self._filter_by_type_and_state(
            Paper,
            {
                PublicationState.SUBMITTED_TO_JOURNAL,
                PublicationState.PUBLISHED,
            },
        )

    @property
    def confnotes(self) -> list[ConfNote]:
        """Get all CONF notes (no filtering)."""
        return [a for a in self._analyses.values() if isinstance(a, ConfNote)]

    @property
    def confnotes_filtered(self) -> list[ConfNote]:
        """Get all published CONF notes."""
        return self._filter_by_type_and_state(ConfNote, {PublicationState.PUBLISHED})

    @property
    def pubnotes(self) -> list[PubNote]:
        """Get all PUB notes (no filtering)."""
        return [a for a in self._analyses.values() if isinstance(a, PubNote)]

    @property
    def pubnotes_filtered(self) -> list[PubNote]:
        """Get all published PUB notes."""
        return self._filter_by_type_and_state(PubNote, {PublicationState.PUBLISHED})

    def determine_last_modified_time(self) -> str:
        """Determine the last modified time of the analysis and paper CSV files.

        This method checks the last modified time of the analysis and paper
        CSV files and returns the most recent timestamp as a formatted string.
        The timestamp is converted to the "Europe/Zurich" timezone.
        If the files are not found, a warning is logged and the method returns
        a default message indicating that the files were not found.

        Returns:
            str: The last modified time as a formatted string.

        """
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
