# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Explain view diagnostics by cause, severity and observable page inclusion."""

DEFINITIONS = {
    "unknown_state": ("Uncertain lifecycle state", "warning"),
    "missing_publication": ("Unresolved publication links", "warning"),
    "conflicting_analysis": ("Conflicting analysis relationships", "warning"),
    "missing_analysis": ("Unresolved analysis links", "warning"),
    "missing_public_identifier": ("Missing public note identifiers", "warning"),
    "one_way_publication": ("One-way publication links", "info"),
    "other_relationship": ("Other relationship issues", "warning"),
}
RELATIONSHIP_CODES = {
    "unresolved publication link": "missing_publication",
    "publication points to a different analysis": "conflicting_analysis",
    "unresolved relatedAnalysis": "missing_analysis",
    "one-way publication link": "one_way_publication",
}
EFFECTS = {
    "missing_publication": "Publication state and milestones are unavailable for this link; analysis classification and progress may be incomplete.",
    "conflicting_analysis": "Conflicting outbound link ignored; the publication-owned relationship takes precedence.",
    "missing_analysis": "Linked-analysis fallback for affiliations and metadata is unavailable; directly recorded publication fields remain usable.",
    "missing_public_identifier": "No final note identifier is available; the record cannot meet the released-note archive criterion.",
    "one_way_publication": "Analysis state and progress use the outbound publication link; no reciprocal relatedAnalysis was recorded.",
    "other_relationship": "See the recorded relationship evidence; the effect is not classified.",
}


def placement(trace):
    """Describe actual inclusion separately from a diagnostic's potential effect."""
    analysis = trace["resource"] == "analyses"
    inclusion = trace.get("inclusion" if analysis else "archive_inclusion", {}).get(
        "value"
    )
    if inclusion is None:
        return "Page inclusion not established"
    page = "ongoing analyses" if analysis else "publication archive"
    return ("Included in " if inclusion else "Excluded from ") + page


def diagnostic_entry(trace):
    """Summarize one record's actionable issues without its full derivation trace."""
    issues = []
    if trace["state"]["value"] == "unknown":
        issues.append(
            {
                "kind": "state",
                "reason": trace["state"]["reason"],
                "inputs": trace["state"]["inputs"],
            }
        )
    for issue in trace.get("relationship_issues", []):
        issues.append({"kind": "relationship", **issue})
    if trace.get("relationship_issue"):
        issues.append(
            {
                "kind": "relationship",
                "reason": trace["relationship_issue"],
                "link": trace.get("relatedAnalysis"),
            }
        )
    if trace.get("public_identifier_issue"):
        issues.append({"kind": "public_identifier", **trace["public_identifier_issue"]})
    if not issues:
        return None
    reasons = []
    for issue in issues:
        code = (
            "unknown_state"
            if issue["kind"] == "state"
            else "missing_public_identifier"
            if issue["kind"] == "public_identifier"
            else RELATIONSHIP_CODES.get(issue["reason"], "other_relationship")
        )
        issue["code"] = code
        issue["level"] = DEFINITIONS[code][1]
        issue["effect"] = (
            "Excluded from ongoing analyses until the lifecycle state can be established."
            if code == "unknown_state" and trace["resource"] == "analyses"
            else "Excluded from the publication archive until submission or release can be established."
            if code == "unknown_state"
            else EFFECTS[code]
        )
    for issue in issues:
        reason = issue["reason"]
        status = issue.get("inputs", {}).get("status")
        if status is not None:
            reason += f" (source status: {status!r})"
        link = issue.get("link") or {}
        if link:
            reason += f" ({link.get('type', 'unknown type')}: {link.get('referenceCode', 'missing identifier')})"
        related = issue.get("relatedAnalysis") or {}
        if related:
            reason += f"; publication's related analysis: {related.get('referenceCode', 'missing identifier')}"
        reasons.append(reason)
        issue["message"] = reason
    return {
        "resource": trace["resource"],
        "reference": trace["reference"],
        "state": trace["state"]["value"],
        "placement": placement(trace),
        "reasons": reasons,
        "issues": issues,
    }


def group_diagnostics(entries):
    """One section per cause; issue and unique-record counts are distinct."""
    groups = {}
    for entry in entries:
        for issue in entry["issues"]:
            code = issue["code"]
            title, level = DEFINITIONS[code]
            group = groups.setdefault(
                code, {"code": code, "title": title, "level": level, "entries": []}
            )
            group["entries"].append(
                {
                    "resource": entry["resource"],
                    "reference": entry["reference"],
                    "placement": entry["placement"],
                    "message": issue["message"],
                    "effect": issue["effect"],
                }
            )
    result = []
    for code in DEFINITIONS:
        if code not in groups:
            continue
        group = groups[code]
        group["entries"].sort(
            key=lambda entry: (entry["resource"], entry["reference"], entry["message"])
        )
        group["issue_count"] = len(group["entries"])
        group["record_count"] = len(
            {(entry["resource"], entry["reference"]) for entry in group["entries"]}
        )
        result.append(group)
    return result
