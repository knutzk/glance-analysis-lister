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

Each entry maps the duplicate to the record that supersedes it. Both are
checked on every run: an entry that is no longer unaccounted for, or that has
left the registry, is reported so that this file does not silently rot.

"""

KnownDuplicates = {
    # Reason: Shell record: it carries the editorial board, the contact editors and
    # the supporting document of TOPQ-2018-17, but not one review date of its
    # own. TOPQ-2018-17 was published on 2020-06-12 as arXiv:1910.08819.
    "TOPQ-2019-27": "TOPQ-2018-17",
    # Reason: Created on 2021-02-02 with review dates from 2018/2019 that predate its
    # own phase 0 start, and identical field for field to TOPQ-2018-03. The
    # analysis was published as TOPQ-2020-06 on 2023-08-16.
    "TOPQ-2021-02": "TOPQ-2018-03",
    # Reason: Identical field for field to TOPQ-2018-14, with review dates
    # predating its own phase 0 start (the same pattern as TOPQ-2021-02 above).
    "TOPQ-2021-03": "TOPQ-2018-14",
}
