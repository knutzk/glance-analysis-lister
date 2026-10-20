# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Analysis records that duplicate another record in GLANCE.

An analysis that finishes phase 0 without a paper, CONF note or PUB note
record appears on no page, and `GlanceRegistry.log_unaccounted()` reports it
so that the GLANCE record can be completed. Some of those entries are not
incomplete but duplicated: the analysis was registered a second time, and it
is the other record that carries the publication.

Closing a duplicate in GLANCE is the real fix, and it needs rights on the
record that we do not have. Until someone with them gets to it, the entries
listed here are reported as INFO rather than as a warning, so that a genuinely
incomplete record still stands out.

Each entry maps an unused duplicate to a related record. Closed records are
expected to stay out of the views. A duplicate acquiring an active or
publication record needs review. Verified clone origins belong in clones.py;
those relationships are handled by the registry itself.

"""

KnownDuplicates = {
    # Reason: Shell record: it carries the editorial board, the contact editors and
    # the supporting document of TOPQ-2018-17, but not one review date of its
    # own. TOPQ-2018-17 was published on 2020-06-12 as arXiv:1910.08819.
    "TOPQ-2019-27": "TOPQ-2018-17",
}
