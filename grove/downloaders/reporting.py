# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Consistent command summaries without exposing downloaded records or credentials."""

import logging
from hashlib import file_digest
from pathlib import Path
from time import perf_counter

from ..console import print_summary

logger = logging.getLogger(__name__)


def _file_state(path):
    """Fingerprint output bytes; inability to inspect is not evidence of safety."""
    try:
        with path.open("rb") as stream:
            return ("present", file_digest(stream, "sha256").hexdigest())
    except FileNotFoundError:
        return ("missing", None)
    except OSError:
        return ("unknown", None)


def _failure_state(paths, before, *, marker, recovery_dir, recovery_pattern):
    try:
        interrupted = marker is not None and marker.exists()
    except OSError:
        interrupted = None
    if interrupted:
        logger.error(
            "Output state: incomplete HTML batch; marker=%s. Do not consume these CSVs; rerun download-html to repair the batch.",
            marker,
        )
    elif interrupted is None:
        logger.error(
            "Output state: unable to inspect the HTML interruption marker; verify the batch before use."
        )
    else:
        after = [_file_state(path) for path in paths]
        if any(state[0] == "unknown" for state in [*before, *after]):
            logger.error(
                "Output state: could not verify all output files; inspect the destination before use."
            )
        elif before == after:
            logger.error(
                "Output state: previous download output preserved byte-for-byte."
                if any(state[0] == "present" for state in before)
                else "Output state: no new download output published."
            )
        else:
            logger.error(
                "Output state: files differ from their pre-download state; inspect the destination before use."
            )
    try:
        recovery = sorted(Path(recovery_dir).glob(recovery_pattern))
    except OSError:
        logger.error("Recovery files: unable to inspect %s", recovery_dir)
    else:
        if recovery:
            for path in recovery:
                logger.error("Recovery files retained: %s", path)
        else:
            logger.error("Recovery files: none found in %s", recovery_dir)


def run_download(
    operation,
    *,
    kind,
    destination,
    files,
    validation,
    color="auto",
    marker=None,
    recovery_dir,
    recovery_pattern,
    saved_html=None,
):
    """Run one CLI workflow and describe successful publication or failure state.

    Elapsed time includes authentication and publication. Existing outputs are
    inspected before the operation and again on failure; checks do not promise
    an initially incomplete or invalid output was usable. No retries or recovery
    mutations happen here. The original exception is always propagated.
    """
    paths = [Path(path) for path in files]
    started = perf_counter()
    before = [_file_state(path) for path in paths]
    logger.info("Starting %s download; output=%s", kind, destination)
    try:
        counts = operation()
    except BaseException:
        logger.error(
            "%s download failed after %.2fs; output=%s",
            kind,
            perf_counter() - started,
            destination,
        )
        _failure_state(
            paths,
            before,
            marker=marker,
            recovery_dir=recovery_dir,
            recovery_pattern=recovery_pattern,
        )
        if saved_html is not None:
            logger.error("Saved diagnostic HTML may be partial: %s", saved_html)
        raise
    details = [
        ("Output", destination),
        ("Files", ", ".join(path.name for path in paths)),
        *counts.items(),
        ("Total records", sum(counts.values())),
        (
            "Elapsed",
            f"{perf_counter() - started:.2f}s (including authentication and publication)",
        ),
        ("Validation", validation),
    ]
    if saved_html is not None:
        details.append(("Saved HTML", saved_html))
    print_summary(f"{kind} download complete", details, color=color)
    return counts
