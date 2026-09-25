"""Glance registry module.


This module provides the GlanceRegistry class, which is responsible for
loading and enriching ATLAS analysis records from CSV files. It provides
programmatic access to the complete and filtered sets of analyses,
papers, CONF notes, and PUB notes. The class supports filtering by
publication state and type, and includes utilities to determine file
modification timestamps.

"""

import csv
import json
import logging
import re
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from attrs import asdict

from ..lookup_dicts.known_duplicates import KnownDuplicates
from ..lookup_dicts.validation import validate_lookups
from ..storage import atomic_write_text, require_complete_csv_batch
from .analysis import Analysis
from .confnote import ConfNote
from .enums import PublicationState
from .field_maps import (
    REQUIRED_COLUMNS_ANALYSIS,
    REQUIRED_COLUMNS_CONFNOTE,
    REQUIRED_COLUMNS_PAPER,
    REQUIRED_COLUMNS_PUBNOTE,
)
from .paper import Paper
from .pubnote import PubNote

logger = logging.getLogger(__name__)

# Papers published before this year are left to the TWiki rather than listed.
# Kept as a constant so that a snapshot written without one is restored with
# the same cut instead of an empty string, which would compare smaller than
# every date and quietly pull in every paper the top WG has ever published.
DEFAULT_THRESHOLD_YEAR = "2020"


class _FilteringMixin:
    """Mixin class to provide filtering and counting methods for analyses.

    The class it is mixed into provides `_analyses`, the dictionary that all
    methods here read.

    """

    def count(self, predicate: Callable[[Analysis], bool]) -> int:
        """Count entries matching a custom filter predicate."""
        return len(self.filter(predicate))

    def count_by_state(
        self, predicate: Callable[[Analysis], bool]
    ) -> dict[PublicationState, int]:
        """Count entries matching a custom filter predicate grouped by publication state."""
        counts = dict.fromkeys(PublicationState, 0)
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
        threshold_year=DEFAULT_THRESHOLD_YEAR,
    ):
        logger.info("Initializing GlanceRegistry...")
        validate_lookups()
        self.analysis_path = Path(csv_dir) / analysis_csv
        self.paper_path = Path(csv_dir) / paper_csv
        self.confnote_path = Path(csv_dir) / confnote_csv
        self.pubnote_path = Path(csv_dir) / pubnote_csv
        self.threshold_year = threshold_year
        self._analyses: dict[str, Analysis] = {}

        require_complete_csv_batch(Path(csv_dir))
        self.last_modified_time = self._determine_last_modified_time()
        self._load_and_enrich()
        require_complete_csv_batch(Path(csv_dir))

    def __repr__(self):
        return f"<GlanceRegistry: {len(self._analyses)} analyses>"

    def __str__(self):
        summary = "GlanceRegistry: "
        summary += f"{len(self.analyses)} ongoing analyses, "
        summary += f"{len(self.papers)} submitted/published papers, "
        summary += f"{len(self.confnotes)} CONF notes, "
        summary += f"{len(self.pubnotes)} PUB notes"
        return summary

    # --- Public API Methods ---

    @classmethod
    def from_json(cls, path: Path):
        """Create a GlanceRegistry instance from a previously stored JSON file."""
        validate_lookups()
        # Mapping from string type to class
        cls_map = {
            "Analysis": Analysis,
            "Paper": Paper,
            "ConfNote": ConfNote,
            "PubNote": PubNote,
        }

        # Load JSON data
        with open(path, encoding="utf8") as f:
            raw_data = json.load(f)

        # Create a new instance without calling __init__
        self = cls.__new__(cls)
        self.analysis_path = None
        self.paper_path = None
        self.confnote_path = None
        self.pubnote_path = None
        self._analyses = {}

        # Reconstruct the entries using type tags
        for ref_code, entry_dict in raw_data["entries"].items():
            type_str = entry_dict.pop("_entrytype", "Analysis")
            entry_cls = cls_map.get(type_str, Analysis)
            self._analyses[ref_code] = entry_cls.from_json(entry_dict)

        self.last_modified_time = raw_data.get("last_modified_time", "")
        self.threshold_year = raw_data.get("threshold_year") or DEFAULT_THRESHOLD_YEAR

        return self

    def get(self, ref_code: str) -> Analysis | None:
        """Get an analysis by its reference code."""
        return self._analyses.get(ref_code)

    def store_json(self, path: Path):
        """Store the registry as a JSON file with serialized entries and metadata.

        This file is committed and diffed on every GLANCE refresh, so each
        analysis is written on its own single line rather than through a
        blanket `indent=4`, which scatters every field of every entry across
        its own line. One line per `ref_code` keeps the diff limited to the
        analyses that actually changed. `json.dump` can't mix indent levels
        within one call, so the outer `{"entries": {...}, ...}` skeleton is
        assembled by hand here; every token in it still goes through
        `json.dumps`, and the result is parsed back before being written to
        catch any mistake in that assembly.

        """

        def serializer(instance, field, value):
            if isinstance(value, Enum):
                return value.value
            return value

        entry_lines = [
            f"        {json.dumps(ref_code)}: "
            + json.dumps(
                {
                    "_entrytype": type(entry).__name__,
                    **asdict(entry, value_serializer=serializer),
                },
                ensure_ascii=False,
            )
            for ref_code, entry in sorted(self._analyses.items())
        ]

        content = (
            "{\n"
            '    "entries": {\n'
            + ",\n".join(entry_lines)
            + ("\n" if entry_lines else "")
            + "    },\n"
            f'    "last_modified_time": {json.dumps(self.last_modified_time)},\n'
            f'    "threshold_year": {json.dumps(self.threshold_year)}\n'
            "}\n"
        )

        # Guard against a mistake in the hand-assembled skeleton above: this
        # must round-trip to the same entries the standard encoder would
        # have produced.
        parsed = json.loads(content)
        assert parsed["entries"].keys() == self._analyses.keys()

        atomic_write_text(path, content)

        logger.info("Stored registry as JSON file at %s", path)

    # --- Public Properties: Access to Data ---

    @property
    def analyses(self) -> list[Analysis | Paper | ConfNote | PubNote]:
        """All analyses that are ongoing/under review.

        Some of these entries may have been promoted to papers or notes, but
        if they are still in the review process, they are included here.

        """
        return self.filter(lambda a: a.is_ongoing())

    @property
    def confnotes(self) -> list[ConfNote]:
        """All entries that should be listed as CONF note."""
        return self.filter(
            lambda a: (
                isinstance(a, ConfNote) and a.pub_state == PublicationState.PUBLISHED
            )
        )

    @property
    def entries(self) -> dict[str, Analysis | Paper | ConfNote | PubNote]:
        """Direct access to the internal registry dictionary."""
        return self._analyses.copy()

    @property
    def papers(self) -> list[Paper]:
        """All entries that should be listed as paper.

        This includes all papers that are either in SUBMITTED_TO_JOURNAL state
        or PUBLISHED with a publication date greater than the threshold year.

        """
        return self.filter(
            lambda a: (
                isinstance(a, Paper)
                and (
                    a.pub_state == PublicationState.SUBMITTED_TO_JOURNAL
                    or (
                        a.pub_state == PublicationState.PUBLISHED
                        and a.date_publication >= self.threshold_year
                    )
                )
            )
        )

    @property
    def unaccounted(self) -> list[Analysis | Paper | ConfNote | PubNote]:
        """All entries that no page lists and that no filter meant to drop.

        Most entries the pages leave out are left out on purpose: an analysis
        that was closed, a note that a later publication superseded, a paper
        older than the threshold year. The two states below are different —
        they mean that the record finished phase 0 without ever turning up in
        the papers, CONF note or PUB note table, or that its status strings
        made no sense to us. Either way the entry silently exists nowhere,
        which is worth reporting rather than filtering away.

        """
        return self.filter(
            lambda a: (
                a.pub_state in {PublicationState.PAST_PHASE0, PublicationState.UNKNOWN}
            )
        )

    @property
    def pubnotes(self) -> list[PubNote]:
        """All entries that should be listed as PUB note."""
        return self.filter(
            lambda a: (
                isinstance(a, PubNote) and a.pub_state == PublicationState.PUBLISHED
            )
        )

    # --- Internal Load and Enrich ---

    def _determine_last_modified_time(self) -> str:
        """Return the latest modification timestamp for CSV files as string."""
        max_timestamp = 0
        for path in [
            self.analysis_path,
            self.paper_path,
            self.confnote_path,
            self.pubnote_path,
        ]:
            try:
                ts = path.stat().st_mtime
                max_timestamp = max(max_timestamp, ts)
            except FileNotFoundError:
                continue

        # Formatting a timestamp of 0 would put "Jan 01, 1970" on every page
        # rather than admitting that there was nothing to read it from.
        if not max_timestamp:
            logger.warning("No CSV file found, cannot determine the sync time.")
            return "unknown"

        last_modified = datetime.fromtimestamp(
            max_timestamp, tz=ZoneInfo("Europe/Zurich")
        )
        return last_modified.strftime("%b %d, %Y, %H:%M (%Z)")

    def _enrich(self, path: Path, cls, key: str, prefix: str = "") -> tuple[int, int]:
        """Enrich the stored analyses with the data of one CSV file.

        Args:
            path: Path of the CSV file to read.
            cls: Class to enrich the matching analyses with.
            key: Column that holds the reference code of a row.
            prefix: Prefix to strip off that reference code.

        Returns:
            The number of enriched analyses, and the number of rows without
            a matching analysis.

        """
        n_enriched = 0
        n_unmatched = 0
        columns = {
            Paper: REQUIRED_COLUMNS_PAPER,
            ConfNote: REQUIRED_COLUMNS_CONFNOTE,
            PubNote: REQUIRED_COLUMNS_PUBNOTE,
        }[cls]
        for row in self._read_csv_rows(path, columns, key=key, prefix=prefix):
            ref = row[key].removeprefix(prefix)
            base = self._analyses.get(ref)
            if base is None:
                n_unmatched += 1
            elif self._may_enrich(base, cls, ref):
                self._analyses[ref] = cls.from_analysis_and_dict(base, row)
                n_enriched += 1

        return n_enriched, n_unmatched

    def _may_enrich(self, base: Analysis, cls, ref: str) -> bool:
        """Return whether an entry may be (re-)enriched with `cls` data.

        A record can be listed in several GLANCE tables, and enriching it
        replaces it wholesale: ConfNote and PubNote derive from Analysis, not
        from Paper, so enriching a paper with note data would drop everything
        the paper knows. Enriching a bare analysis is the normal case; beyond
        that only the paper may take over, as it supersedes its own CONF note.
        Any other collision is unexpected and leaves the entry as it is.

        Every collision is reported: the paper/CONF note pair as INFO, since
        it is a normal step of the publication life cycle, everything else as
        a warning.

        Args:
            base: The entry that is already stored for this reference code.
            cls: The class the entry would be enriched with.
            ref: Reference code of the entry, for the log messages.

        Returns:
            True if the entry may be replaced, False if it must be kept.

        """
        if type(base) is Analysis:
            return True

        # The paper wins over its CONF note, no matter which of the two GLANCE
        # tables is read first.
        if {type(base), cls} == {Paper, ConfNote}:
            logger.info(
                "%s is listed as paper and as CONF note, keeping the paper "
                "and dropping the CONF note data.",
                ref,
            )
            return cls is Paper

        if type(base) is cls:
            logger.warning(
                "%s is listed twice as %s, keeping the first entry. "
                "Check the GLANCE record.",
                ref,
                cls.__name__,
            )
            return False

        logger.warning(
            "%s is listed as %s and as %s, keeping the %s and dropping the "
            "%s data. Check the GLANCE record.",
            ref,
            type(base).__name__,
            cls.__name__,
            type(base).__name__,
            cls.__name__,
        )
        return False

    def _load_and_enrich(self):
        # Load the analysis database from the CSV file.
        logger.info("Loading list of analyses from file %s", self.analysis_path.name)
        self._analyses = {
            a.ref_code: a for a in self._load_data(self.analysis_path, Analysis)
        }
        logger.info("Loaded %d analysis base entries.", len(self._analyses))

        # Load papers from the CSV file and enrich corresponding analysis entries.
        logger.info("Loading list of papers from file %s", self.paper_path.name)
        enriched, unmatched = self._enrich(self.paper_path, Paper, key="Reference Code")
        self._log_enrichment("paper", enriched, unmatched, len(self.papers))

        # Load CONF notes from the CSV files and enrich corresponding analysis entries.
        logger.info("Loading list of CONF notes from file %s", self.confnote_path.name)
        enriched, unmatched = self._enrich(
            self.confnote_path, ConfNote, key="Temporary Reference Code", prefix="CONF-"
        )
        self._log_enrichment("CONF note", enriched, unmatched, len(self.confnotes))

        # Load PUB notes from the CSV files and enrich corresponding analysis entries.
        logger.info("Loading list of PUB notes from file %s", self.pubnote_path.name)
        enriched, unmatched = self._enrich(
            self.pubnote_path, PubNote, key="Temporary Reference Code", prefix="PUB-"
        )
        self._log_enrichment("PUB note", enriched, unmatched, len(self.pubnotes))

        self.log_unaccounted()

    def log_unaccounted(self):
        """Report the entries that end up on no page at all.

        Entries listed in `lookup_dicts.known_duplicates` are reported as
        INFO instead: they duplicate another GLANCE record and only closing
        them there would settle it, so warning about them every run would
        only bury a record that is genuinely incomplete.

        """
        unaccounted = self.unaccounted
        duplicates = [a for a in unaccounted if a.ref_code in KnownDuplicates]
        incomplete = [a for a in unaccounted if a.ref_code not in KnownDuplicates]

        if incomplete:
            logger.warning(
                "%d entries appear on no page, because they finished phase 0 "
                "without a paper, CONF note or PUB note record in GLANCE: %s",
                len(incomplete),
                ", ".join(f"{a.ref_code} ({a.pub_state.value})" for a in incomplete),
            )

        if duplicates:
            logger.info(
                "%d further entries appear on no page, but are known to "
                "duplicate a record that does: %s",
                len(duplicates),
                ", ".join(
                    f"{a.ref_code} (superseded by {KnownDuplicates[a.ref_code]})"
                    for a in duplicates
                ),
            )

        self._log_stale_duplicates({a.ref_code for a in unaccounted})

    def _log_stale_duplicates(self, unaccounted_refs: set):
        """Report entries of the known-duplicates table that no longer apply.

        The table exists because the duplicates cannot be closed in GLANCE.
        Once one of them is, it stops being unaccounted for and its entry
        here is dead weight that would go on suppressing a warning nobody
        asked it to.

        Args:
            unaccounted_refs: Reference codes that no page lists.

        """
        stale = []
        for ref, superseded_by in KnownDuplicates.items():
            if ref not in self._analyses:
                stale.append(f"{ref} (no longer in GLANCE)")
            elif ref not in unaccounted_refs:
                stale.append(f"{ref} ({self._analyses[ref].pub_state.value} now)")

            if superseded_by not in self._analyses:
                stale.append(f"{ref} (superseding {superseded_by} is not in GLANCE)")

        if stale:
            logger.warning(
                "%d entries of known_duplicates.py no longer apply and can be "
                "removed: %s",
                len(stale),
                ", ".join(stale),
            )

    @staticmethod
    def _log_enrichment(label: str, enriched: int, unmatched: int, listed: int):
        """Report the outcome of one enrichment step.

        Args:
            label: Name of the enrichment type, for the log message.
            enriched: Number of analyses that were enriched.
            unmatched: Number of rows without a matching analysis.
            listed: Number of enriched entries that the pages end up listing.

        """
        logger.info(
            "Enriched %d analyses with %s data, of which %d are listed on the "
            "pages. %d %s rows had no matching analysis.",
            enriched,
            label,
            listed,
            unmatched,
            label,
        )

    def _load_data(self, path: Path, cls):
        rows = self._read_csv_rows(
            path, REQUIRED_COLUMNS_ANALYSIS, key="Reference Code", prefix="ANA-"
        )
        data = [cls.from_csv_dict(row) for row in rows]
        return sorted(data, key=lambda x: x.ref_code)

    def _read_csv_rows(
        self, path: Path, required_columns=(), *, key=None, prefix=""
    ) -> list[dict[str, str]]:
        """Return the rows of one CSV file.

        All four files are required. Carrying on without one of them used to
        cost the pages a whole category — every paper, or every note — and
        the run reported that as a plain count, which reads exactly like a
        quiet week in the top WG. Failing here instead keeps a half-read
        download out of the committed snapshot.

        Args:
            path: Path of the CSV file to read.

        Returns:
            One dictionary per row of the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If headers, row widths, identifiers, or uniqueness are
                invalid, or the file holds no rows. Values are never stripped.

        """
        try:
            with open(path, encoding="utf8", newline="") as f:
                reader = csv.DictReader(f, strict=True)
                headers = reader.fieldnames or []
                duplicates = [h for h, n in Counter(headers).items() if n > 1]
                missing = sorted(set(required_columns) - set(headers))
                if duplicates or missing or any(not h for h in headers):
                    raise ValueError(
                        f"{path}: invalid CSV headers; missing={missing}, "
                        f"duplicates={duplicates}, empty headers={'' in headers}"
                    )
                rows = []
                seen = {}
                for row in reader:
                    line = reader.line_num
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(
                            f"{path}: line {line}: wrong number of CSV fields"
                        )
                    if key is not None:
                        ref = row[key].removeprefix(prefix)
                        if not re.fullmatch(r"[A-Z][A-Z0-9]+-\d{4}-\d+", ref):
                            raise ValueError(
                                f"{path}: line {line}: invalid {key}: {row[key]!r}"
                            )
                        if ref in seen:
                            raise ValueError(
                                f"{path}: line {line}: duplicate identifier {ref}; "
                                f"first seen on line {seen[ref]}"
                            )
                        seen[ref] = line
                    rows.append(row)
        except csv.Error as exc:
            raise ValueError(
                f"{path}: line {reader.line_num}: invalid CSV: {exc}"
            ) from exc
        except FileNotFoundError:
            raise FileNotFoundError(
                f"{path} not found. Re-run download_csv_files.py (step 1)."
            ) from None

        if not rows:
            raise ValueError(
                f"{path} holds no rows. GLANCE probably returned a login page; "
                "refresh the cookies and re-run download_csv_files.py (step 1)."
            )

        return rows
