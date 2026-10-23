# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build group pages and a derivation report from one immutable input snapshot."""

import json
import logging
from pathlib import Path

from ..registry import CuratedRegistry
from .assets import asset_documents
from .markdown.pages import (
    confnotes_page,
    ongoing_page,
    papers_page,
    pubnotes_page,
)
from .prepare import prepare_group
from .report import build_report
from .writer import write_documents

logger = logging.getLogger(__name__)


def render_group(snapshot, output_dir, profile):
    if profile.publication_policy is None:
        print(
            f"WARNING: No publication curation configuration for {profile.group}; using only its internal identifier group token."
        )
    raw = Path(snapshot).read_bytes()
    registry = CuratedRegistry(json.loads(raw))
    view = prepare_group(registry, profile)
    report = build_report(view, snapshot, raw)
    counts = report["counts"]
    documents = {
        "ongoing.md": ongoing_page(view),
        "papers.md": papers_page(view),
        "confnotes.md": confnotes_page(view),
        "pubnotes.md": pubnotes_page(view),
        "view-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    documents.update(asset_documents())
    write_documents(output_dir, documents, snapshot=snapshot)
    review_keys = {
        (entry["resource"], entry["reference"])
        for entry in report["analyses_needing_review"]
    }
    for entry in report["records_with_diagnostics"]:
        needs_review = (entry["resource"], entry["reference"]) in review_keys
        label = (
            "Needs review (also counted in diagnostics; excluded from ongoing)"
            if needs_review
            else "Diagnostics"
        )
        logger.warning(
            "%s: %s/%s: %s",
            label,
            entry["resource"],
            entry["reference"],
            "; ".join(entry["reasons"]),
        )
    return counts
