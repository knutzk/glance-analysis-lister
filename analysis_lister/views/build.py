# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Build group pages and a derivation report from one immutable input snapshot."""

import json
import logging
from pathlib import Path

from ..provenance import generator_fingerprint, generator_revision, markdown_provenance
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
    revision = generator_revision()
    report["generator"] = {
        "name": "glance-analysis-lister",
        "git_commit": revision,
        "content_sha256": generator_fingerprint(),
    }
    counts = report["counts"]
    documents = {
        "ongoing.md": ongoing_page(view, revision=revision),
        "papers.md": papers_page(view, revision=revision),
        "confnotes.md": confnotes_page(view, revision=revision),
        "pubnotes.md": pubnotes_page(view, revision=revision),
        "view-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    for name in tuple(documents):
        if name.endswith(".md"):
            documents[name] = markdown_provenance(
                documents[name],
                revision=revision,
                snapshot=snapshot,
                sha256=report["snapshot"]["sha256"],
                profile_sha256=report["profile_sha256"],
                generator_sha256=report["generator"]["content_sha256"],
            )
    documents.update(asset_documents(revision))
    publication = write_documents(output_dir, documents, snapshot=snapshot)
    logger.info(
        "Rendered outputs: %d written, %d unchanged",
        publication["written"],
        publication["unchanged"],
    )
    for group in report["diagnostic_groups"]:
        log = logger.warning if group["level"] == "warning" else logger.info
        log(
            "%s: %d issue(s) across %d record(s)",
            group["title"],
            group["issue_count"],
            group["record_count"],
        )
        for entry in group["entries"]:
            log(
                "%s/%s — %s: %s Effect: %s",
                entry["resource"],
                entry["reference"],
                entry["placement"],
                entry["message"],
                entry["effect"],
            )
    return counts
