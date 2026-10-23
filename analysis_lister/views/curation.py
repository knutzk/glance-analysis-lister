# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""User-configured publication curation, independent of analysis affiliation."""

import re
import tomllib
from pathlib import Path

from attrs import asdict

from .models import Decision
from .profiles import PublicationPolicy


def load_publication_policy(path, group):
    if path is None:
        return None
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if set(data) != {"groups"} or not isinstance(data["groups"], dict):
        raise ValueError("Curation config requires a groups table")
    fields = {"title", "keywords", "groups", "subgroups"}
    for name, policy in data["groups"].items():
        if not isinstance(policy, dict) or set(policy) - fields:
            raise ValueError(
                f"Group {name} accepts only title, groups, subgroups and keywords"
            )
        if "title" in policy and (
            not isinstance(policy["title"], str) or not policy["title"].strip()
        ):
            raise ValueError(f"Group {name} title must be a nonempty string")
        for key in fields - {"title"}:
            values = policy.get(key, [])
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(
                    f"Group {name} {key} must be a list of nonempty strings"
                )
    if group not in data["groups"]:
        return None
    policy = data["groups"][group]
    return PublicationPolicy(
        title=policy.get("title", ""),
        **{
            key: tuple(policy.get(key, []))
            for key in ("groups", "subgroups", "keywords")
        },
    )


def identifier_matches(reference, group):
    return bool(
        re.search(r"(?:^|-)" + re.escape(group) + r"(?:-|$)", reference, re.IGNORECASE)
    )


def archive_curation(reference, profile, keywords, affiliations, subgroups):
    policy = profile.publication_policy or PublicationPolicy()
    allowed = {word.strip().casefold() for word in policy.keywords}
    matched = [word for word in keywords.value if word.strip().casefold() in allowed]
    identifier_match = profile.publication_policy is None and identifier_matches(
        reference, profile.group
    )
    groups = affiliations.value
    recorded_groups = [groups.get("leadingGroup"), *(groups.get("otherGroups") or [])]
    group_matches = [
        name
        for name in policy.groups
        if identifier_matches(reference, name) or name in recorded_groups
    ]
    subgroup_matches = [name for name in policy.subgroups if name in subgroups.value]
    return Decision(
        "archive-configured-curation/v3",
        identifier_match or bool(matched or group_matches or subgroup_matches),
        "OR of configured groups, subgroups and keywords; absent configuration uses only the internal group token",
        {
            "group": profile.group,
            "internal_reference": reference,
            "identifier_match": identifier_match,
            "keyword_evidence": asdict(keywords),
            "matching_keywords": matched,
            "configured_keywords": list(policy.keywords),
            "configured_groups": list(policy.groups),
            "configured_subgroups": list(policy.subgroups),
            "matching_groups": group_matches,
            "matching_subgroups": subgroup_matches,
            "affiliation_evidence": asdict(affiliations),
            "subgroup_evidence": asdict(subgroups),
        },
    )


def archive_curation_statement(profile):
    if profile.publication_policy is None:
        return f"No publication curation configuration was supplied for {profile.group}. Include publications whose internal identifier contains the {profile.group} group token."
    return "Include a publication if ANY listed criterion matches: a group (internal identifier token or leading/additional affiliation), a leading/additional subgroup (exact name), or a keyword (exact case-insensitive match)."
