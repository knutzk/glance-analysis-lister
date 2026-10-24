# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Offline integration with stare's actual client, models and JSON serializers.

All response data is invented independently of GLANCE snapshots. HTTP is replaced
at the transport boundary; authentication storage and network are never used.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx
from stare import Glance
from stare.settings import StareSettings

from analysis_lister.downloaders.api import (
    collect_registry,
    download_registry,
    publish_registry,
)
from analysis_lister.registry.enrichment import curate
from analysis_lister.registry.schema import validate_api_registry, validate_registry

ENDPOINTS = {
    "/searchAnalysis": "analyses",
    "/searchPaper": "papers",
    "/searchConfnote": "confnotes",
    "/searchPubnote": "pubnotes",
}


def response_records(count=3):
    """Small, detailed API-shaped responses for each of the four real models."""
    result = {resource: [] for resource in ENDPOINTS.values()}
    for number in range(1, count + 1):
        team = [
            {
                "firstName": "Invented",
                "lastName": "Editor",
                "isContactEditor": True,
                "isAnalysisContact": True,
            }
        ]
        base = {
            "shortTitle": "Invented integration fixture",
            "analysisTeam": team,
            "metadata": {"keywords": [{"name": "Invented keyword"}]},
            "groups": {"leadingGroup": {"name": "DEMO"}},
        }
        result["analyses"].append(
            {
                **base,
                "referenceCode": f"ANA-DEMO-2099-{number:02}",
                "status": "Phase 0 Active",
                "creationDate": "2099-01-01",
                "extraMetadata": {"invented": "preserved"},
                "relatedPublications": [
                    {"type": "Paper", "referenceCode": f"DEMO-2099-{number:02}"}
                ],
                "phase0": {
                    "state": "Expression of interest (EOI) meeting data",
                    "eoiMeetings": [
                        {
                            "date": "2099-01-02T12:30:00+00:00",
                            "title": "Invented meeting",
                            "link": {
                                "label": "Agenda",
                                "url": "https://example.test/meeting",
                            },
                        }
                    ],
                    "preApprovalMeetings": [{"date": "2099-01-03T12:30:00+00:00"}],
                },
            }
        )
        result["papers"].append(
            {
                **base,
                "referenceCode": f"DEMO-2099-{number:02}",
                "status": "Publication Phase Finished",
                "phase1": {"draftReleasedDate": "2099-01-04"},
                "publicationPhase": {
                    "publishedOnlineDate": "2099-02-01T12:30:00+00:00"
                },
            }
        )
        for resource, prefix in (("confnotes", "CONF"), ("pubnotes", "PUB")):
            result[resource].append(
                {
                    **base,
                    "temporaryReferenceCode": f"{prefix}-DEMO-2099-{number:02}",
                    "finalReferenceCode": f"{'ATLAS-CONF' if resource == 'confnotes' else 'ATL-PHYS-PUB'}-2099-{number:03}",
                    "status": "Phase 1 Finished",
                    "relatedAnalysis": {
                        "type": "Analysis",
                        "referenceCode": f"ANA-DEMO-2099-{number:02}",
                    },
                    "phase1": {
                        "releaseDate": "2099-02-02",
                        "publicWebPageUrlForFiguresAndTables": "https://example.test/note",
                    },
                }
            )
    return result


class StareIntegrationTests(unittest.TestCase):
    def test_real_detailed_models_round_trip_into_api_and_curated_storage(self):
        records = response_records()
        requests = []

        def respond(request):
            endpoint = next(
                path for path in ENDPOINTS if request.url.path.endswith(path)
            )
            resource = ENDPOINTS[endpoint]
            requests.append((resource, dict(request.url.params)))
            offset, limit = (
                int(request.url.params[key]) for key in ("offset", "limit")
            )
            return httpx.Response(
                200,
                json={
                    "numberOfResults": len(records[resource]),
                    "results": records[resource][offset : offset + limit],
                },
            )

        settings = StareSettings(
            base_url="https://example.test/api", cache_enabled=False
        )
        with (
            patch(
                "stare.client.httpx.HTTPTransport",
                return_value=httpx.MockTransport(respond),
            ),
            patch(
                "stare.client.TokenManager",
                side_effect=AssertionError("credentials must not be accessed"),
            ),
            Glance(settings=settings, token="invented-offline-token") as client,
        ):
            result = collect_registry(client, page_size=2, client_version="0.6.1")
        self.assertEqual(
            [name for name, _ in requests],
            ["analyses"] * 2 + ["papers"] * 2 + ["confnotes"] * 2 + ["pubnotes"] * 2,
        )
        self.assertEqual(result["counts"], dict.fromkeys(records, 3))
        analysis = result["analyses"][0]
        self.assertEqual(analysis["creationDate"], "2099-01-01")
        self.assertEqual(analysis["extraMetadata"], {"invented": "preserved"})
        self.assertNotIn("reference_code", analysis)
        phase = analysis["phase0"]
        self.assertNotIn("meetings", phase)
        self.assertEqual(len(phase["eoiMeetings"]), 1)
        self.assertEqual(len(phase["preApprovalMeetings"]), 1)
        self.assertEqual(
            phase["eoiMeetings"][0]["link"]["url"], "https://example.test/meeting"
        )
        self.assertIsInstance(phase["eoiMeetings"][0]["date"], str)
        self.assertTrue(
            result["papers"][0]["publicationPhase"]["publishedOnlineDate"].startswith(
                "2099-02-01T"
            )
        )
        self.assertEqual(
            result["confnotes"][0]["temporaryReferenceCode"], "CONF-DEMO-2099-01"
        )
        self.assertEqual(
            result["pubnotes"][0]["temporaryReferenceCode"], "PUB-DEMO-2099-01"
        )
        validate_api_registry(result)
        curated = curate(result, {})
        validate_registry(curated)
        self.assertEqual(
            curated["analyses"][0]["gal_contactEditors"], ["Invented Editor"]
        )
        self.assertEqual(
            curated["analyses"][0]["phase0"]["gal_eoiMeetingDates"], ["2099-01-02"]
        )
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "registry.json"
            publish_registry(result, destination)
            self.assertEqual(json.loads(destination.read_text()), result)

    def test_real_model_validation_failure_does_not_publish_or_expose_payload(self):
        records = response_records(1)
        records["papers"][0]["referenceCode"] = "invented-sensitive-invalid-identifier"

        def respond(request):
            resource = next(
                resource
                for path, resource in ENDPOINTS.items()
                if request.url.path.endswith(path)
            )
            return httpx.Response(
                200, json={"numberOfResults": 1, "results": records[resource]}
            )

        settings = StareSettings(
            base_url="https://example.test/api", cache_enabled=False
        )
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "registry.json"
            destination.write_bytes(b"existing snapshot must remain unchanged")
            with (
                patch(
                    "stare.client.httpx.HTTPTransport",
                    return_value=httpx.MockTransport(respond),
                ),
                patch("stare.settings.StareSettings", return_value=settings),
                patch(
                    "stare.auth.TokenManager",
                    return_value=Mock(
                        get_token=Mock(return_value="invented-offline-token")
                    ),
                ),
                self.assertRaises(ValueError) as caught,
            ):
                download_registry(destination)
            self.assertEqual(
                destination.read_bytes(), b"existing snapshot must remain unchanged"
            )
            self.assertNotIn("invented-sensitive", str(caught.exception))
            self.assertIn("no registry published", str(caught.exception))
