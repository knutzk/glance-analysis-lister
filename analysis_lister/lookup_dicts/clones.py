# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Verified clone and duplicate origins: analysis reference -> original reference.

Cloning alone does not supersede a publication. The registry uses publication
attachments and the directed lineage to decide which records remain visible.
"""

Clones = {
    # Reason: Duplicate shell carrying the editorial board, contact editors and
    # supporting document of TOPQ-2018-17 without its own review dates. The
    # publication is attached to TOPQ-2018-17 (arXiv:1910.08819).
    "TOPQ-2019-27": "TOPQ-2018-17",
    # Source: GLANCE analysis detail pages checked 2026-10-20 explicitly list
    # TOPQ-2020-06 as a clone of TOPQ-2018-03.
    "TOPQ-2020-06": "TOPQ-2018-03",
    # Source: GLANCE analysis detail pages checked 2026-10-20 explicitly list
    # TOPQ-2021-02 as a clone of TOPQ-2018-03.
    "TOPQ-2021-02": "TOPQ-2018-03",
    # Source: GLANCE analysis detail pages checked 2026-10-20 explicitly list
    # TOPQ-2021-03 as a clone of TOPQ-2018-14.
    "TOPQ-2021-03": "TOPQ-2018-14",
}
