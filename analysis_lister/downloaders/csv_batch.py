# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Transactional publication of HTML-derived CSV batches."""

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from .html import DownloadTable, staged_csv_files
from .manifest import CSV_REFRESH_MARKER, HTML_MANIFEST

logger = logging.getLogger(__name__)


def publish_csv_batch(
    staging: Path,
    output_dir: Path,
    filenames: list[str],
):
    """Publish a validated batch, restoring the old files on a write failure.

    The marker identifies an interrupted promotion for downstream CSV consumers.
    Backups remain in the staging directory if the process is killed outright.
    A fresh successful download repairs such an interrupted promotion.
    Do not read or publish this batch concurrently.
    """
    backup = staging / "previous"
    backup.mkdir()
    for name in filenames:
        old = output_dir / name
        if old.exists():
            shutil.copy2(old, backup / name)

    marker = output_dir / CSV_REFRESH_MARKER
    was_interrupted = marker.exists()
    marker.write_text("Download incomplete; re-run analysis-lister download-html.\n")
    replaced = []
    try:
        for name in filenames:
            replaced.append(name)
            (staging / name).replace(output_dir / name)
    except BaseException:
        for name in reversed(replaced):
            previous = backup / name
            if previous.exists():
                previous.replace(output_dir / name)
            else:
                (output_dir / name).unlink(missing_ok=True)
        if not was_interrupted:
            marker.unlink()
        raise
    marker.unlink()


def download_html_csvs(
    tasks: Sequence[DownloadTable],
    csv_dir: Path,
    debug_dir: Path,
    *,
    cookies: dict[str, str] | None = None,
    use_local_html: bool = False,
    debug: bool = False,
) -> dict[str, int]:
    """Fetch and publish CSVs only, for the standalone download command."""
    with staged_csv_files(
        tasks,
        csv_dir,
        debug_dir,
        cookies=cookies,
        use_local_html=use_local_html,
        debug=debug,
    ) as (staging, counts):
        publish_csv_batch(
            staging,
            csv_dir,
            [t.csv_filename for t in tasks] + [HTML_MANIFEST],
        )
    logger.info("Published complete HTML CSV batch: %s", csv_dir)
    return counts
