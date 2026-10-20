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
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # editorial board.
    "EXOT-2019-38": "EXOT-2018-08",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching editorial board.
    "HDBS-2019-26": "HDBS-2018-18",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "HIGG-2021-03": "HIGG-2018-04",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "HIGG-2021-04": "HIGG-2018-14",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "HION-2021-02": "HION-2018-04",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "HION-2021-03": "HION-2018-03",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, analysis contacts, internal note editors.
    "HION-2021-04": "HION-2018-27",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "HION-2021-06": "HION-2019-05",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching contact editors,
    # editorial board, analysis contacts, internal note editors.
    "HION-2021-07": "HION-2019-02",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching contact editors.
    "SIMU-2018-03": "SIMU-2020-01",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board.
    "SUSY-2019-20": "SUSY-2018-06",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "SUSY-2021-01": "SUSY-2018-33",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "SUSY-2021-02": "SUSY-2018-17",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board, analysis contacts, internal note editors.
    "SUSY-2021-03": "SUSY-2018-22",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching supporting documents,
    # contact editors, editorial board.
    "TOPQ-2019-25": "TOPQ-2018-01",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: unique published-paper
    # counterpart with identical short title and matching contact editors.
    "TOPQ-2019-26": "TOPQ-2017-17",
    # Source: Saved GLANCE CSVs reviewed 2026-10-20: titles differ slightly,
    # but supporting documents, contact editors, editorial board and internal
    # note editors match the published-paper record exactly.
    "HION-2021-05": "HION-2019-09",
}
