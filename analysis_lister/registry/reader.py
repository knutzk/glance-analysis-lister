# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Read curated records and explicit relationships without applying view policies."""

import copy
import json
from collections.abc import Mapping
from pathlib import Path

from .schema import RESOURCES, record_key, validate_registry

LINK_RESOURCES = {
    "Analysis": "analyses",
    "Paper": "papers",
    "CONF note": "confnotes",
    "PUB note": "pubnotes",
}


class CuratedRegistry:
    """Own a validated snapshot and index each independent resource by native ID.

    Returned records are copies: editing them cannot invalidate the indexes.
    Loading never enriches records, filters them, or resolves external metadata.
    """

    def __init__(self, data):
        validate_registry(data)
        self._data = copy.deepcopy(data)
        self._indexes = {
            resource: {
                record_key(record, resource): record for record in self._data[resource]
            }
            for resource in RESOURCES
        }

    @classmethod
    def from_json(cls, path):
        """Load and validate a saved curated snapshot, entirely offline."""
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def metadata(self):
        """Return container metadata without the four resource collections."""
        return copy.deepcopy(
            {key: value for key, value in self._data.items() if key not in RESOURCES}
        )

    def records(self, resource):
        """Return every record of one resource in snapshot order, without filtering."""
        return tuple(
            copy.deepcopy(record) for record in self._indexes[resource].values()
        )

    def get(self, resource, reference):
        """Look up a native identifier; return None if the record is absent."""
        return copy.deepcopy(self._indexes[resource].get(reference))

    def resolve_link(self, link):
        """Follow an explicit API relationship; leave dangling links unresolved.

        Pass a relatedAnalysis object or an item from relatedPublications.
        Unknown relationship types are rejected rather than guessed from IDs.
        """
        if not isinstance(link, Mapping):
            raise ValueError("Relationship must be an object")
        kind = link.get("type")
        resource = LINK_RESOURCES.get(kind) if isinstance(kind, str) else None
        reference = link.get("referenceCode")
        if resource is None or not isinstance(reference, str) or not reference:
            raise ValueError("Relationship requires a known type and referenceCode")
        return self.get(resource, reference)
