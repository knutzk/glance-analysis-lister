# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build group pages and a derivation report from one immutable input snapshot."""

import json
import logging
from importlib.resources import files
from pathlib import Path

from ..registry import CuratedRegistry
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
    if profile.archive_groups is None:
        print(
            f"WARNING: No publication curation configuration for {profile.group}; using only its internal identifier group token."
        )
    raw = Path(snapshot).read_bytes()
    registry = CuratedRegistry(json.loads(raw))
    view = prepare_group(registry, profile)
    report = build_report(view, snapshot, raw)
    counts = report["counts"]
    issues = counts["records_with_diagnostics"]
    documents = {
        "ongoing.md": ongoing_page(view),
        "papers.md": papers_page(view),
        "confnotes.md": confnotes_page(view),
        "pubnotes.md": pubnotes_page(view),
        "view-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    for name in (
        "gal-views.css",
        "gal-views.js",
        "gal-publications.css",
        "gal-publications.js",
        "gal-confnotes.css",
        "gal-confnotes.js",
    ):
        documents["assets/" + name] = (
            files("analysis_lister.views")
            .joinpath("assets", name)
            .read_text(encoding="utf-8")
        )
    write_documents(output_dir, documents, snapshot=snapshot)
    if issues:
        logger.warning(
            "%d affiliated records have state or relationship diagnostics; inspect view-report.json",
            issues,
        )
    return counts
