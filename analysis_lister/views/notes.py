# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Interpret recorded note details, CDS links and explicit supersession."""

import re
from urllib.parse import urlsplit

from attrs import asdict

from .models import Decision
from .people import board_names


def note_cds_record(record, resource):
    """Use the recorded CDS record URL; do not guess a URL from note identifiers."""
    raw = (record.get("phase1") or {}).get("draftCdsUrl")
    value = None
    if isinstance(raw, str):
        try:
            parsed = urlsplit(raw.strip())
            if (
                parsed.scheme in {"https", "http"}
                and parsed.hostname in {"cds.cern.ch", "cdsweb.cern.ch"}
                and re.fullmatch(r"/records?/\d+/?", parsed.path)
            ):
                value = raw.strip()
        except ValueError:
            pass
    return Decision(
        ("conf-note" if resource == "confnotes" else "pub-note") + "-cds-record",
        value,
        "recorded phase-1 CDS record link with HTTP(S) and a CDS record path; absent or invalid URLs stay empty",
        {"phase1.draftCdsUrl": raw},
    )


def note_expansion(record, resource):
    """Prepare recorded note people, supersession and auxiliary metadata."""
    phase = record.get("phase1") or {}
    metadata = record.get("metadata") or {}
    paths = {
        "Analysis contacts": (
            "gal_analysisContacts",
            record.get("gal_analysisContacts") or [],
        ),
        "Contact editors": (
            "gal_contactEditors",
            record.get("gal_contactEditors") or [],
        ),
        "Editorial board": (
            "phase1.gal_editorialBoard",
            phase.get("gal_editorialBoard") or [],
        ),
        "Editorial-board chairs": (
            "phase1.gal_editorialBoardChairs",
            phase.get("gal_editorialBoardChairs") or [],
        ),
        "Ex-officio editorial board": (
            "phase1.gal_editorialBoardExOfficio",
            phase.get("gal_editorialBoardExOfficio") or [],
        ),
        "First sign-off responsible": (
            "phase1.gal_firstSignOffResponsible",
            phase.get("gal_firstSignOffResponsible") or [],
        ),
        "Second sign-off responsible": (
            "phase1.gal_secondSignOffResponsible",
            phase.get("gal_secondSignOffResponsible") or [],
        ),
    }

    if resource == "pubnotes":
        paths = {
            "Analysis contacts": paths["Analysis contacts"],
            "Contact editors": paths["Contact editors"],
            **{
                label: ("phase1." + field, phase.get(field) or [])
                for label, field in (
                    ("Readers", "gal_readers"),
                    ("First readers", "gal_firstReaders"),
                    ("Second readers", "gal_secondReaders"),
                )
            },
        }

    def name_list(value):
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return (
            [name.strip() for name in value if isinstance(name, str) and name.strip()]
            if isinstance(value, (list, tuple))
            else []
        )

    people = []
    chairs = name_list(paths.get("Editorial-board chairs", ("", []))[1])
    for label, (_, names) in paths.items():
        names = name_list(names)
        if label == "Editorial-board chairs":
            continue  # Chairs are marked in the combined board list.
        if label == "Editorial board":
            names = board_names(names, chairs)
        people.append({"label": label, "names": list(names)})
    tools = [
        item.get("name") if isinstance(item, dict) else item
        for item in metadata.get("mvaMlTools") or []
    ]
    collisions = []
    for entry in metadata.get("collisions") or []:
        if not isinstance(entry, dict):
            continue
        parts = [entry.get("year"), entry.get("run"), entry.get("type")]
        for value_key, unit_key in (
            ("ecmValue", "ecmUnit"),
            ("luminosityValue", "luminosityUnit"),
        ):
            value = entry.get(value_key)
            if value:
                parts.append(
                    " ".join(str(v) for v in (value, entry.get(unit_key)) if v)
                )
        if any(parts):
            collisions.append(" · ".join(str(part) for part in parts if part))
    supersession = note_supersession(record, resource)
    return Decision(
        ("conf-note" if resource == "confnotes" else "pub-note") + "-expansion",
        {
            "people": people,
            "tags": [
                {
                    "label": "MVA / ML tools",
                    "values": list(
                        dict.fromkeys(t for t in tools if isinstance(t, str) and t)
                    ),
                },
                {"label": "Collisions", "values": list(dict.fromkeys(collisions))},
            ],
            "superseded": supersession.value,
            "superseded_by": [
                dict(link)
                for link in record.get("supersededBy") or []
                if isinstance(link, dict)
            ],
            "related_analysis": record.get("relatedAnalysis"),
        },
        "direct recorded names; board chairs marked and deduplicated; readable metadata labels; explicit supersession links; missing values remain empty",
        {
            **dict(paths.values()),
            "metadata.mvaMlTools": metadata.get("mvaMlTools"),
            "metadata.collisions": metadata.get("collisions"),
            "supersession": asdict(supersession),
            "relatedAnalysis": record.get("relatedAnalysis"),
        },
    )


def note_supersession(record, resource):
    links = record.get("supersededBy") or []
    return Decision(
        ("conf-note" if resource == "confnotes" else "pub-note") + "-supersession",
        bool(links),
        "superseded when the source records a replacing publication/analysis link; target resolution is not required; no inference from title or date",
        {"supersededBy": links},
    )
