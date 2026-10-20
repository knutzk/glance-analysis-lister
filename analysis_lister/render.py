# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Render analysis pages from a local registry snapshot."""

import logging
from pathlib import Path

from analysis_lister.diagnostics import lookup_report
from analysis_lister.glance.glance_registry import GlanceRegistry
from analysis_lister.markdown.mkdown_renderer import MarkdownPageRenderer

logger = logging.getLogger(__name__)


@lookup_report()
def render_pages(snapshot_path: Path, output_dir: Path):
    registry = GlanceRegistry.from_json(snapshot_path)
    registry.log_unaccounted()
    logger.info("Rendering %s", registry)
    output_dir.mkdir(parents=True, exist_ok=True)
    MarkdownPageRenderer(
        registry=registry, output_dir=output_dir, threshold_year=registry.threshold_year
    ).write_all()
