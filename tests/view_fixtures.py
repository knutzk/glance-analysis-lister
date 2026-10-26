# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Independently invented records shared by unit and browser checks."""

from analysis_lister.registry.enrichment import curate
from analysis_lister.registry.schema import RESOURCES


def person(first, last="Example", **roles):
    return {
        "firstName": first,
        "lastName": last,
        "cernCcid": "invented-id",
        "email": "invented@example.test",
        **roles,
    }


def api_fixture():
    records = {
        "analyses": {"referenceCode": "ANA-DEMO-2099-01"},
        "papers": {"referenceCode": "DEMO-2099-01"},
        "confnotes": {"temporaryReferenceCode": "CONF-DEMO-2099-01"},
        "pubnotes": {"temporaryReferenceCode": "PUB-DEMO-2099-01"},
    }
    source = {
        "schema": "glance-api-registry",
        "schema_version": 1,
        "fetched_at": "2099-01-10T12:00:00+00:00",
        "source": {
            "selection": "all-accessible",
            "base_url": "https://example.test/api",
        },
        "counts": dict.fromkeys(RESOURCES, 1),
    }
    for resource, record in records.items():
        record.update(
            {
                "analysisTeam": [
                    person("Current", isAnalysisContact=True, isContactEditor=True),
                    person("Current", isAnalysisContact=True),
                    person(
                        "Former",
                        isAnalysisContact=True,
                        analysisContactAssignment={"endDate": "2099-01-09"},
                    ),
                    person(
                        "Future",
                        isAnalysisContact=True,
                        analysisContactAssignment={"startDate": "2099-01-11"},
                    ),
                    person("Editor", isContactEditor=True),
                    person("Member"),
                ],
                "metadata": {
                    "keywords": [
                        {"name": "Keyword"},
                        {"name": "Keyword"},
                        {"name": "Other"},
                    ]
                },
                "phase0" if resource == "analyses" else "phase1": {
                    "editorialBoard": [
                        person("Chair", isChair=True),
                        person("Observer", isExOfficio=True),
                    ],
                    "signOffResponsible": person("Official"),
                    "startDate": "2099-01-01",
                },
                "relatedPublications": [
                    {"referenceCode": "DEMO-2099-01", "type": "Paper"}
                ],
                "documentation": {
                    "repositories": [{"url": "https://example.test/code"}]
                },
            }
        )
        source[resource] = [record]
    return source


def analysis(number, *, group="DEMO", status="Phase 0 Active", additional=()):
    return {
        "referenceCode": f"ANA-DEMO-2099-{number:02}",
        "status": status,
        "shortTitle": "Invented | title [link] <tag>",
        "gal_analysisContacts": ["Example Contact"],
        "gal_contactEditors": [],
        "gal_groups": {
            "leadingGroup": group,
            "otherGroups": list(additional),
            "leadingSubgroup": "Example subgroup, with comma",
            "subgroups": [],
        },
        "metadata": {"gal_keywords": ["Synthetic"]},
        "phase0": {"startDate": "2099-01-01", "gal_editorialBoard": []},
        "relatedPublications": [],
    }


def publication(
    number,
    *,
    resource="papers",
    group="DEMO",
    related=None,
    status="Publication Phase Finished",
    date="2099-02-01",
):
    key = "referenceCode" if resource == "papers" else "temporaryReferenceCode"
    prefix = {"papers": "", "confnotes": "CONF-", "pubnotes": "PUB-"}[resource]
    value = {
        key: f"{prefix}DEMO-2099-{number:02}",
        "status": status,
        "shortTitle": "Synthetic publication",
        "publicShortTitle": "Synthetic public title",
        "gal_analysisContacts": [],
        "gal_contactEditors": [],
        "gal_groups": {
            "leadingGroup": group,
            "otherGroups": [],
            "leadingSubgroup": None,
            "subgroups": [],
        },
        "relatedAnalysis": {"type": "Analysis", "referenceCode": related}
        if related
        else None,
    }
    if resource == "papers":
        value["publicationPhase"] = {
            "publishedOnlineDate": date,
            "arXivSubmissionDate": None,
            "gal_dois": [
                {"doi": "10.9999/synthetic", "citation": "Synthetic citation"}
            ],
        }
    else:
        value["finalReferenceCode"] = (
            f"{'ATLAS-CONF' if resource == 'confnotes' else 'ATL-PHYS-PUB'}-2099-{number:03}"
        )
        value["phase1"] = {
            "releaseDate": date,
            "publicWebPageUrlForFiguresAndTables": "https://example.test/note",
        }
    return value


def snapshot(*analyses, papers=(), confnotes=(), pubnotes=()):
    data = curate(api_fixture())
    data["analyses"] = list(analyses) or [analysis(99, group="OTHER", status="Closed")]
    for resource, records in (
        ("papers", papers),
        ("confnotes", confnotes),
        ("pubnotes", pubnotes),
    ):
        fallback = publication(99, resource=resource, group="OTHER", status="Closed")
        fallback[
            "referenceCode" if resource == "papers" else "temporaryReferenceCode"
        ] = "OTHER-2099-99"
        data[resource] = list(records) or [fallback]
    data["counts"] = {
        key: len(data[key]) for key in ("analyses", "papers", "confnotes", "pubnotes")
    }
    return data
