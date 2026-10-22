# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Legacy import path; DOI processing is owned by the curated registry."""

from ..registry.doi import doi_from_url, format_url_dois, order_doi_urls

__all__ = ["doi_from_url", "format_url_dois", "order_doi_urls"]
