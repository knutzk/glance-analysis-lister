# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Analysis identifiers intentionally excluded from output and diagnostics.

Entries stay in snapshots. Reasons document reviewed exceptions without changing
GLANCE metadata or inferring publication links.
"""

IgnoredAnalyses = {
    # Source: Maintainer confirmed 2026-10-20; publication has a different identifier.
    "HIGG-2020-13": "Publication retained independently under its PUB identifier.",
    # Source: Saved GLANCE metadata reviewed 2026-10-20; publication uses another ID.
    "HIGG-2021-27": "Publication identifier differs from the analysis identifier.",
    # Source: Maintainer confirmed 2026-10-20 that this effort was abandoned.
    "MDET-2020-03": "Abandoned after phase 0.",
    # Source: Maintainer confirmed 2026-10-20 that this effort was abandoned.
    "PIXE-2019-02": "Abandoned after phase 0.",
    # Source: Maintainer confirmed 2026-10-20 that the paper was never completed.
    "STDM-2021-03": "Historical publication linkage; paper abandoned.",
}
