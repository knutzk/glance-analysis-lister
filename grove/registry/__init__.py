# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Curated registry access; construction is available from registry.builder."""

from .reader import CuratedRegistry
from .schema import RESOURCES, SCHEMA, validate_registry

__all__ = [
    "CuratedRegistry",
    "RESOURCES",
    "SCHEMA",
    "validate_registry",
]
