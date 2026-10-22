# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Transactional publication of supplemental HTML-derived CSV batches."""

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from ..storage import CSV_REFRESH_MARKER, SUPPLEMENT_MANIFEST
from .html import DownloadTable, staged_csv_files
from .scope import SCOPE_FILENAME, RetrievalScope

logger = logging.getLogger(__name__)


def publish_csv_batch(
    staging: Path,
    output_dir: Path,
    filenames: list[str],
):
    """Publish a validated batch, restoring the old files on a write failure.

    The marker makes an interrupted promotion detectable by the registry loader.
    Backups remain in the staging directory if the process is killed outright.
    A fresh successful download repairs such an interrupted promotion.
    Run downloading and registry building sequentially.
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
    scope: RetrievalScope | None = None,
) -> None:
    """Fetch and publish CSVs only, for the standalone download command."""
    with staged_csv_files(
        tasks,
        csv_dir,
        debug_dir,
        cookies=cookies,
        use_local_html=use_local_html,
        debug=debug,
        scope=scope,
    ) as staging:
        publish_csv_batch(
            staging,
            csv_dir,
            [t.csv_filename for t in tasks]
            + [SCOPE_FILENAME]
            + (
                [SUPPLEMENT_MANIFEST]
                if (staging / SUPPLEMENT_MANIFEST).exists()
                else []
            ),
        )
    logger.debug("Published complete CSV batch.")
