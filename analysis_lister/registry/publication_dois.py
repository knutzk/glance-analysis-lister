# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Extract API paper DOIs and embed cached citations without network access."""

from urllib.parse import unquote, urlsplit

from ..citation_store import citation_record, normalize_doi
from .doi import order_doi_urls


def paper_dois(paper):
    """Read authoritative publication links; ignore other publication websites."""
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
        candidates = []
        if isinstance(link, dict):
            label = link.get("label")
            if isinstance(label, str) and label.strip().lower().startswith("doi:"):
                candidates.append(label)
        if value:
            if isinstance(value, str) and value.strip().lower().startswith(
                ("https://", "http://")
            ):
                parsed = urlsplit(value.strip())
                if (parsed.hostname or "").lower() in {
                    "doi.org",
                    "www.doi.org",
                    "dx.doi.org",
                    "www.dx.doi.org",
                }:
                    candidates.append(value)
                elif "/doi/" in parsed.path:
                    candidates.append(unquote(parsed.path.split("/doi/", 1)[1]))
            else:
                candidates.append(value)
        for candidate in candidates:
            try:
                doi = normalize_doi(candidate)
            except ValueError:
                malformed += 1
                continue
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
