# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Copy-ready paper citations prepared entirely from saved publication fields."""

import re
from urllib.parse import urlsplit

from .models import Decision
from .publication_states import publication_state


def arxiv_reference(url):
    """Use the identifier in a recognized arXiv URL; preserve other URLs as text."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if parsed.hostname in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(
            r"/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)(?:\.pdf)?/?",
            parsed.path,
        )
        if match:
            return "arXiv:" + match[1]
    return url


def paper_citation(record):
    """Keep DOI/citation pairs in curated order, with later entries on own lines."""
    phase = record.get("publicationPhase") or {}
    title = (
        phase.get("finalTitleTex")
        or record.get("fullTitle")
        or record.get("shortTitle")
        or record["referenceCode"]
    )
    lines = ["ATLAS Collaboration", title]
    dois = phase.get("grove_dois") or []
    references = []
    if dois and dois[0].get("citation"):
        references.append(dois[0]["citation"])
    elif (
        not dois
        and publication_state(record, "papers").value == "submitted"
        and phase.get("finalSubmissionJournal")
    ):
        references.append("Submitted to " + phase["finalSubmissionJournal"])
    references.extend(
        dict.fromkeys(
            arxiv_reference(item["url"])
            for item in phase.get("arXivUrls") or []
            if item.get("url")
        )
    )
    if references:
        lines.append(", ".join(references))
    for index, entry in enumerate(dois):
        doi = entry.get("doi") or entry.get("url")
        parts = [
            entry.get("citation") if index else None,
            "DOI: " + doi if doi else None,
        ]
        text = ", ".join(part for part in parts if part)
        if text:
            lines.append("[" + text + "]" if index else text)
    return Decision(
        "paper-cite-as",
        lines,
        "ATLAS citation using final TeX title, then full title, short title or native identifier; saved references in curated order with no external lookup",
        {
            "publicationPhase.finalTitleTex": phase.get("finalTitleTex"),
            "fullTitle": record.get("fullTitle"),
            "shortTitle": record.get("shortTitle"),
            "referenceCode": record["referenceCode"],
            "status": record.get("status"),
            "publicationPhase": phase,
        },
    )
