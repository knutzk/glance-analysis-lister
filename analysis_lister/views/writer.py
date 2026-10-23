# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publish fully rendered documents without overwriting the input snapshot."""

from pathlib import Path

from ..storage import atomic_write_text


def write_documents(output_dir, documents, *, snapshot):
    output_dir, snapshot = Path(output_dir), Path(snapshot).resolve()
    paths = [output_dir / name for name in documents]
    if any(path.resolve() == snapshot for path in paths):
        raise ValueError("View output must not overwrite the registry snapshot")
    for name, content in documents.items():
        atomic_write_text(output_dir / name, content)
