# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""DOI extraction, deduplication, and publication/correction ordering.

Cached material labels and conservative date inference share this implementation
for curated registry enrichment. Ambiguous order retains the input and emits a notice.
"""

import logging
import re

from ..citations.store import normalize_doi
from ..diagnostics import lookup_notice
from . import store as citation_store

logger = logging.getLogger(__name__)

# Patterns to recover the publication date that a publisher encodes in its
# DOIs. GLANCE lists the DOIs of a paper and of its erratum/addendum in
# arbitrary order, so they have to be sorted by publication date to tell the
# original article from the later correction.
_DOI_DATE_PATTERNS = (
    # JHEP, e.g. 10.1007/JHEP07(2023)203
    re.compile(r"/JHEP(?P<month>\d{2})\((?P<year>\d{4})\)", re.IGNORECASE),
    # Springer EPJ, e.g. 10.1140/epjc/s10052-023-11573-0 (year modulo 1000)
    re.compile(r"/epj\w*/s\d+-(?P<year>\d{3})-"),
    # Elsevier, e.g. 10.1016/j.physletb.2022.137379
    re.compile(r"^10\.1016/j\.\w+\.(?P<year>\d{4})\."),
)


def doi_from_url(url: str) -> str:
    """Return the bare DOI of a doi.org URL (empty string if there is none)."""
    index = url.find("doi.org/")
    return url[index + 8 :] if index >= 0 else ""


def _doi_date(doi: str) -> tuple[int, int]:
    """Return the (year, month) encoded in a DOI, or (0, 0) if undecodable."""
    for pattern in _DOI_DATE_PATTERNS:
        match = pattern.search(doi)
        if not match:
            continue

        year = int(match.group("year"))
        if year < 1000:  # Springer writes the year modulo 1000.
            year += 2000

        groups = match.groupdict()
        return year, int(groups.get("month") or 0)

    return 0, 0


def _ambiguous_dates(dois):
    """Return whether DOI-encoded dates fail to establish a total order."""
    dates = [_doi_date(doi) for doi in dois]
    return any(date == (0, 0) for date in dates) or any(
        year == other_year and (not month or not other_month or month == other_month)
        for i, (year, month) in enumerate(dates)
        for other_year, other_month in dates[i + 1 :]
    )


def order_doi_urls(urls: list[str], ref_code: str, *, citations=None) -> list[str]:
    """Deduplicate and order DOIs, warning when dates cannot resolve the order.

    Missing months cover the entire year, so they overlap any dated DOI in
    that year. A unique cached publication with only known corrections is placed
    first; corrections retain input order if their dates are ambiguous. Otherwise
    unknown or overlapping dates retain input order with a warning.
    """

    # The same DOI may be listed several times, and under both the doi.org and
    # the dx.doi.org host. Deduplicate on the DOI, keeping the first URL.
    by_doi: dict[str, str] = {}
    for url in urls:
        by_doi.setdefault(doi_from_url(url), url)

    # Explicit cached material labels distinguish an original from a correction
    # without guessing publication dates. Dates only refine the relative order of known corrections.
    store = citation_store.Citations if citations is None else citations
    materials = []
    for doi in by_doi:
        entry = store.get(normalize_doi(doi), {})
        materials.append(entry.get("material") if isinstance(entry, dict) else None)
    if materials.count("publication") == 1 and all(
        material in {"publication", "erratum", "addendum", "editorial note"}
        for material in materials
    ):
        original = []
        corrections = {}
        for material, (doi, url) in zip(materials, by_doi.items(), strict=True):
            if material == "publication":
                original.append(url)
            else:
                corrections[doi] = url
        # The original is known. Uncertain chronology among known corrections
        # does not make its identification ambiguous; preserve their input order.
        if not _ambiguous_dates(corrections):
            corrections = dict(
                sorted(corrections.items(), key=lambda pair: _doi_date(pair[0]))
            )
        return original + list(corrections.values())

    ambiguous = _ambiguous_dates(by_doi)
    if len(by_doi) > 1 and ambiguous:
        lookup_notice(
            logger,
            logging.WARNING,
            "%s: ambiguous DOI order (unknown or overlapping dates); keeping "
            "input order. Verify publication/correction metadata in "
            "json/doi_metadata.json: %s",
            ref_code,
            list(by_doi),
        )
        return list(by_doi.values())

    return sorted(by_doi.values(), key=lambda u: _doi_date(doi_from_url(u)))
