# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Extract API paper DOIs and embed cached citations without network access."""

import re
from urllib.parse import unquote, urlsplit

from ..citations.ordering import order_doi_urls
from ..citations.store import citation_record, normalize_doi


def paper_dois(paper):
    """Extract DOIs from URL fields only; labels never supply DOI values."""
    phase = paper.get("publicationPhase") or {}
    if not isinstance(phase, dict):
        raise ValueError("Paper publication phase must be an object")
    links = phase.get("finalJournalPublicationUrls") or []
    if not isinstance(links, list):
        raise ValueError("Paper publication links must be a list")
    result = []
    malformed = 0
    for link in links:
        value = link.get("url") if isinstance(link, dict) else link
        candidate = value
        if isinstance(value, str) and value.strip().lower().startswith(
            ("https://", "http://")
        ):
            parsed = urlsplit(value.strip())
            if (parsed.hostname or "").lower() not in {
                "doi.org",
                "www.doi.org",
                "dx.doi.org",
                "www.dx.doi.org",
            }:
                # Publisher URLs may use /doi/full/10..., /article/10..., etc.
                match = re.search(r"/(10\.\d{4,9}/.+)$", unquote(parsed.path))
                candidate = match.group(1) if match else None
        doi = None
        if candidate:
            try:
                doi = normalize_doi(candidate)
            except ValueError:
                malformed += 1
            else:
                if doi not in result:
                    result.append(doi)
    return result, malformed


def enrich_paper(paper, citations):
    """Keep each original/correction DOI together with its own citation metadata."""
    dois, malformed = paper_dois(paper)
    entries = []
    urls = order_doi_urls(
        [f"https://doi.org/{doi}" for doi in dois],
        paper["referenceCode"],
        citations=citations,
    )
    for url in urls:
        doi = normalize_doi(url)
        entry = {"doi": doi, "url": url, "resolved": doi in citations}
        if doi in citations:
            entry.update(citation_record(citations[doi]))
        entries.append(entry)
    if paper.get("publicationPhase") is not None:
        paper["publicationPhase"]["gal_dois"] = entries
    return entries, malformed
