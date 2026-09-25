"""File publication safeguards for local analysis-list refreshes."""

import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile

CSV_REFRESH_MARKER = ".refresh-in-progress"


def require_complete_csv_batch(directory: Path):
    """Reject a CSV directory whose previous promotion was interrupted."""
    if (directory / CSV_REFRESH_MARKER).exists():
        raise ValueError(
            f"Incomplete CSV refresh in {directory}. "
            "Re-run download_csv_files.py before building the registry."
        )


def atomic_write_text(path: Path, content: str):
    """Replace a file only after its complete UTF-8 contents have been flushed."""
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
