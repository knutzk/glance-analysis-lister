# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Glance registry module.

The registry holds analysis records, applies enrichment rules, and provides
filtered views. Its constructor accepts in-memory entries. Explicit CSV and
JSON factories handle loading; CSV validation and timestamps live in csv_loader.

"""

import json
import logging
from collections.abc import Callable, Iterable, Mapping
from copy import copy
from enum import Enum
from pathlib import Path

from attrs import asdict

from ..diagnostics import lookup_notice
from ..lookup_review import lookup_review_notices
from ..lookup_validation import validate_lookups
from ..retrieval import RetrievalScope
from ..storage import atomic_write_text
from .analysis import Analysis
from .clones import clone_exclusions
from .confnote import ConfNote
from .enums import PublicationState
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
    """In-memory analysis collection with explicit CSV and JSON loading factories."""

    def __init__(
        self,
        entries: Mapping[str, Analysis] | None = None,
        *,
        threshold_year: str = DEFAULT_THRESHOLD_YEAR,
        last_modified_time: str = "",
        retrieval_scope: RetrievalScope | None = None,
    ):
        """Create an in-memory registry, copying the supplied entry mapping.

        Construction performs no file access, lookup validation, or reporting.
        Entry objects are shared; the registry owns its mapping of them.
        """
        self._analyses = dict(entries) if entries is not None else {}
        self.retrieval_scope = retrieval_scope
        self.threshold_year = threshold_year
        self.last_modified_time = last_modified_time
        self.apply_clone_rules()

    def select(self, predicate: Callable[[Analysis], bool]):
        """Return a view with selected entries, preserving full-registry clone rules.

        The mapping is copied; entry objects and snapshot metadata are shared.
        Exclusions stay based on the full lineage even if a superseding record
        falls outside the selection.
        """
        selected = copy(self)
        selected._analyses = {
            ref: entry for ref, entry in self._analyses.items() if predicate(entry)
        }
        selected._clone_exclusions = self._clone_exclusions.intersection(
            selected._analyses
        )
        return selected

    def apply_clone_rules(self):
        """Recompute clone exclusions after metadata or publication enrichment."""
        self._clone_exclusions = clone_exclusions(self._analyses)

    def is_clone_excluded(self, ref_code: str) -> bool:
        """Whether manual clone lineage excludes this entry from output views."""
        return ref_code in self._clone_exclusions

    @classmethod
    def from_csv(
        cls,
        csv_dir: Path,
        *,
        analysis_csv="analyses.csv",
        paper_csv="papers.csv",
        confnote_csv="confnotes.csv",
        pubnote_csv="pubnotes.csv",
        threshold_year=DEFAULT_THRESHOLD_YEAR,
    ):
        """Load, validate, and enrich a complete CSV batch."""
        from .csv_loader import load_csv_registry

        validate_lookups()
        return load_csv_registry(
            cls,
            Path(csv_dir),
            analysis_csv=analysis_csv,
            paper_csv=paper_csv,
            confnote_csv=confnote_csv,
            pubnote_csv=pubnote_csv,
            threshold_year=threshold_year,
        )

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

        entries = {}
        for ref_code, entry_dict in raw_data["entries"].items():
            type_str = entry_dict.pop("_entrytype", "Analysis")
            entry_cls = cls_map.get(type_str, Analysis)
            entries[ref_code] = entry_cls.from_json(entry_dict)

        return cls(
            entries,
            last_modified_time=raw_data.get("last_modified_time", ""),
            threshold_year=raw_data.get("threshold_year") or DEFAULT_THRESHOLD_YEAR,
            retrieval_scope=RetrievalScope.from_dict(raw_data["retrieval_scope"])
            if raw_data.get("retrieval_scope") is not None
            else None,
        )

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

        scope_metadata = (
            f',\n    "retrieval_scope": {json.dumps(self.retrieval_scope.metadata())}'
            if self.retrieval_scope is not None
            else ""
        )
        content = (
            "{\n"
            '    "entries": {\n'
            + ",\n".join(entry_lines)
            + ("\n" if entry_lines else "")
            + "    },\n"
            f'    "last_modified_time": {json.dumps(self.last_modified_time)},\n'
            f'    "threshold_year": {json.dumps(self.threshold_year)}{scope_metadata}\n'
            "}\n"
        )

        # Guard against a mistake in the hand-assembled skeleton above: this
        # must round-trip to the same entries the standard encoder would
        # have produced.
        parsed = json.loads(content)
        assert parsed["entries"].keys() == self._analyses.keys()

        atomic_write_text(path, content)

        logger.debug("Stored registry as JSON file at %s", path)

    # --- Public Properties: Access to Data ---

    @property
    def analyses(self) -> list[Analysis | Paper | ConfNote | PubNote]:
        """All analyses that are ongoing/under review.

        Some of these entries may have been promoted to papers or notes, but
        if they are still in the review process, they are included here.

        """
        return self.filter(
            lambda a: a.is_ongoing() and not self.is_clone_excluded(a.ref_code)
        )

    @property
    def confnotes(self) -> list[ConfNote]:
        """All entries that should be listed as CONF note."""
        return self.filter(
            lambda a: (
                isinstance(a, ConfNote)
                and a.pub_state == PublicationState.PUBLISHED
                and not self.is_clone_excluded(a.ref_code)
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
                and not self.is_clone_excluded(a.ref_code)
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

    # --- In-memory Enrichment ---

    def enrich(
        self,
        rows: Iterable[dict[str, str]],
        cls,
        key: str,
        prefix: str = "",
        *,
        analysis_short_titles: dict[str, str] | None = None,
    ) -> tuple[int, int]:
        """Enrich the stored analyses from validated publication rows.

        Args:
            rows: Validated CSV rows; reading and validation belong to the loader.
            cls: Class to enrich the matching analyses with.
            key: Column that holds the reference code of a row.
            prefix: Prefix to strip off that reference code.
            analysis_short_titles: Original analysis titles, before display escaping.
                PUB matches require an identical, nonempty short title as well
                as the reference suffix.

        Returns:
            The number of enriched analyses, and the number of rows without
            a matching analysis. Unmatched PUB rows are retained independently.

        """
        n_enriched = 0
        n_unmatched = 0
        for row in rows:
            ref = row[key].removeprefix(prefix)
            base = self._analyses.get(ref)
            title = (
                analysis_short_titles.get(ref, "")
                if analysis_short_titles is not None
                else base.title_short
                if base is not None
                else ""
            )
            if base is None:
                if cls is PubNote:
                    self._add_independent_pubnote(row)
                n_unmatched += 1
            elif cls is PubNote and (not title.strip() or row["Short Title"] != title):
                logger.info(
                    "%s: PUB short title differs or is empty; skipping analysis matching.",
                    row[key],
                )
                self._add_independent_pubnote(row)
                n_unmatched += 1
            elif self._may_enrich(base, cls, ref):
                self._analyses[ref] = cls.from_analysis_and_dict(base, row)
                n_enriched += 1

        self.apply_clone_rules()
        return n_enriched, n_unmatched

    def _add_independent_pubnote(self, row):
        note = PubNote.from_csv_dict(row)
        if note.ref_code in self._analyses:
            raise ValueError(f"Duplicate PUB-note identifier: {note.ref_code}")
        self._analyses[note.ref_code] = note

    def _may_enrich(self, base: Analysis, cls, ref: str) -> bool:
        """Return whether an entry may be (re-)enriched with `cls` data.

        A record can be listed in several GLANCE tables, and enriching it
        replaces it wholesale: ConfNote and PubNote derive from Analysis, not
        from Paper, so enriching a paper with note data would drop everything
        the paper knows. Enriching a bare analysis is the normal case; beyond
        that only the paper may take over, as it supersedes its own CONF note.
        Any other collision is unexpected and leaves the entry as it is.

        Every collision is reported: the paper/CONF note pair as DEBUG, since
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
            logger.debug(
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

    def log_unaccounted(self):
        """Report unfinished records not explained by manual clone relationships."""
        incomplete = self.unaccounted

        if incomplete:
            logger.warning(
                "%d entries appear on no page, because they finished phase 0 "
                "without a paper, CONF note or PUB note record in GLANCE: %s",
                len(incomplete),
                ", ".join(f"{a.ref_code} ({a.pub_state.value})" for a in incomplete),
            )

        for level, message in lookup_review_notices(self):
            lookup_notice(logger, level, "%s", message)
