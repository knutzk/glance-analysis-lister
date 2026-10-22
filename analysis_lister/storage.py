# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""File publication safeguards for local analysis-list refreshes."""

import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile

CSV_REFRESH_MARKER = ".refresh-in-progress"
SUPPLEMENT_MANIFEST = "supplement_manifest.json"


def require_complete_csv_batch(directory: Path):
    """Reject a CSV directory whose previous promotion was interrupted."""
    if (directory / CSV_REFRESH_MARKER).exists():
        raise ValueError(
            f"Incomplete CSV refresh in {directory}. "
            "Re-run analysis-lister download-html before building the registry."
        )


def atomic_write_text(path: Path, content: str):
    """Create parent directories and atomically publish flushed UTF-8 contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
