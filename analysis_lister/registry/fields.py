# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Persist only record fields used by view preparation, search and diagnostics.

Selections apply after enrichment. None keeps a leaf value; a dictionary selects
nested fields, including fields within list items. Missing keys and nulls remain
missing or null. This contract deliberately does not import the views package.
"""


def leaves(*names):
    return dict.fromkeys(names)


LINK = leaves("type", "referenceCode")
URL = leaves("label", "url")
GROUPS = leaves("leadingGroup", "otherGroups", "leadingSubgroup", "subgroups")
METADATA = leaves("gal_keywords", "gal_triggers", "gal_statisticalTools")
PEOPLE = leaves(
    "gal_editorialBoard",
    "gal_editorialBoardChairs",
    "gal_editorialBoardExOfficio",
    "gal_firstSignOffResponsible",
    "gal_secondSignOffResponsible",
    "gal_readers",
    "gal_firstReaders",
    "gal_secondReaders",
)
COMMON = {
    **leaves("status", "shortTitle", "gal_analysisContacts", "gal_contactEditors"),
    "gal_groups": GROUPS,
    "metadata": METADATA,
    "documentation": {"supportingInternalDocuments": URL},
}
PUBLICATION = {
    **COMMON,
    "relatedAnalysis": LINK,
    # The complete derived evidence is consumed by publication diagnostics.
    "gal_publicationProvenance": None,
}
NOTE = {
    **PUBLICATION,
    **leaves("temporaryReferenceCode", "finalReferenceCode", "gal_finalReferenceCode"),
    "supersededBy": LINK,
    "metadata": {
        **METADATA,
        "mvaMlTools": leaves("name"),
        "collisions": leaves(
            "year",
            "run",
            "type",
            "ecmValue",
            "ecmUnit",
            "luminosityValue",
            "luminosityUnit",
        ),
    },
    "phase1": {
        **PEOPLE,
        **leaves(
            "releaseDate",
            "draftCdsUrl",
            "publicWebPageUrlForFiguresAndTables",
            "pgcApprovalDate",
        ),
    },
}
RECORD_FIELDS = {
    "analyses": {
        **COMMON,
        "referenceCode": None,
        "relatedPublications": LINK,
        "phase0": leaves(
            "state",
            "startDate",
            "editorialBoardFormedDate",
            "pgcOrSgcSignOffDate",
            "gal_editorialBoard",
            "gal_editorialBoardChairs",
            "gal_eoiMeetingDates",
            "gal_editorialBoardRequestMeetingDates",
            "gal_preApprovalMeetingDates",
            "gal_approvalMeetingDates",
        ),
    },
    "papers": {
        **PUBLICATION,
        **leaves("referenceCode", "gal_figuresUrl"),
        "phase1": {
            **PEOPLE,
            **leaves(
                "startDate",
                "editorialBoardFormedDate",
                "pgcApprovalDate",
                "editorialBoardDraftSignOffDate",
                "languageEditorsSignOffDate",
                "draftReleasedDate",
                "presentationDate",
                "atlasMeetingDate",
                "pubcommSignOffDate",
                "publicWebPageUrlForFiguresAndTables",
            ),
        },
        "phase2": leaves(
            "startDate",
            "editorialBoardDraft2SignOffDate",
            "draft2SentToCernDate",
            "draft2CernSignOffDate",
            "draft2ReleasedDate",
            "editorialBoardRevisedSignOffDate",
            "pubcommChairOrDeputySignOffDate",
            "spokespersonDelegatedSignOffDate",
            "spokespersonOrDeputySignOffDate",
            "paperClosureDate",
        ),
        "publicationPhase": {
            **leaves(
                "startDate",
                "arXivSubmissionDate",
                "firstRefereeReportDate",
                "journalAcceptanceDate",
                "finalSubmissionJournal",
                "firstProofDate",
                "publishedOnlineDate",
            ),
            "arXivUrls": URL,
            "gal_dois": leaves("doi", "url", "citation"),
        },
    },
    "confnotes": NOTE,
    "pubnotes": NOTE,
}


def select_fields(value, fields):
    """Project an enriched record without modifying it or inventing defaults."""
    if fields is None:
        return value
    if isinstance(value, list):
        return [select_fields(item, fields) for item in value]
    if isinstance(value, dict):
        return {
            key: select_fields(item, fields[key])
            for key, item in value.items()
            if key in fields
        }
    return value


def count_fields(value):
    """Count object-key occurrences, including nested objects and list items.

    Repeated keys count once per occurrence; containers and null-valued keys
    count too. Scalar list items are values, not additional fields.
    """
    if isinstance(value, dict):
        return len(value) + sum(count_fields(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_fields(item) for item in value)
    return 0
