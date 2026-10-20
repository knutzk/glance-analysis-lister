# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Compatibility mapping backed by the single versioned JSON citation store.

Citation data belongs in json/doi_metadata.json, not in a Python dictionary.
"""

from ..citation_store import default_store_path, load_store

JournalRefs = load_store(default_store_path())
