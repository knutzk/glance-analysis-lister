# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Ordered assets shared by all generated group views."""

from importlib.resources import files

ASSET_NAMES = tuple(
    f"gal-{name}.css" for name in ("common", "ongoing", "papers", "notes")
) + tuple(f"gal-{name}.js" for name in ("common", "ongoing", "papers", "notes"))


def asset_documents():
    root = files("analysis_lister.views").joinpath("assets")
    return {
        "assets/" + name: root.joinpath(name).read_text(encoding="utf-8")
        for name in ASSET_NAMES
    }
