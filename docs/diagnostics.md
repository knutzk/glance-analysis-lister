# Diagnostic reports

[Documentation overview](README.md)

`render-group` writes `view-report.json` and prints its path to stdout. Generated pages do not
link to it. The report includes selected records and their directly linked
context, so keep it private alongside the source snapshots.

Diagnostics cover uncertain states, missing or conflicting relationships, and
missing public note identifiers. Each entry identifies the record, says whether
it appears on the page, and explains the effect on classification, progress,
affiliations or identifiers. An issue does not necessarily exclude a record:
a published paper can remain included despite a missing analysis link.

One-way publication links are informational when the outbound link works. Other
diagnostic causes are warnings; missing optional display fields are not.
`--quiet` suppresses informational logs, but the report retains those entries.

| Field | Meaning |
| --- | --- |
| `diagnostic_groups` | Issues grouped by cause, with issue counts, distinct-record counts and affected entries. |
| `counts.warning_issues`, `counts.informational_issues` | Numbers of issues, not distinct records. |
| `counts.records_with_diagnostics` | Number of distinct records with issues, including informational cases. |
| `records_with_diagnostics` | Diagnostic entries, one per affected record. |
| `analyses_needing_review` | Analyses needing review; may overlap with the diagnostic record list. |

Reports use schema version 2. They also record source timestamps, the input hash,
effective policy, rule identifiers, controls and derivation evidence. See
[provenance](provenance.md#profile-and-generator-hashes) for profile and generator
hashes.

## Supported report summary

Automation may depend on the following fields in reports generated under this
contract. The remainder of the report is diagnostic detail, not a stable external
API. This boundary keeps counts and input identification usable without freezing
every internal rule trace.

| Field | Type and meaning |
| --- | --- |
| `schema` | String `"glance-group-view-report"`. |
| `schema_version` | Integer `2`, independent of the package and curated-schema versions. |
| `snapshot.filename` | Input basename, without its directory. |
| `snapshot.sha256` | SHA-256 of the exact input bytes, as 64 lowercase hexadecimal characters. |
| `profile.group` | The selected main-group string. |
| `profile_sha256` | SHA-256 of the effective profile, as 64 lowercase hexadecimal characters. |
| `generator.name` | String `"glance-analysis-lister"`. |
| `generator.git_commit` | Revision string, possibly with `-dirty`, or `unknown` when unavailable. |
| `generator.content_sha256` | Generator content hash, as 64 lowercase hexadecimal characters. |
| `counts` | Object containing the nonnegative integer counts below. |

| Count | Meaning |
| --- | --- |
| `ongoing_analyses` | Analysis rows on the ongoing page. |
| `analyses_needing_review` | Analysis rows needing classification review. |
| `publication_records` | Selected publication records, including those not ready for the archive. |
| `archive_publications` | Submitted/published papers and released notes across the three publication pages, including superseded notes hidden by default. |
| `records_with_diagnostics` | Distinct records with reported issues. |
| `warning_issues` | Warning-level issues, not records or failed commands. |
| `informational_issues` | Informational issues, not records. |

The analysis categories and diagnostic categories can overlap; do not add them
to infer a total. Counts are determined before browser filters. A successful
render can contain warnings and still exit zero.

Within report schema v2, these fields retain their names, types and meanings.
Additional fields are allowed at every level. Consumers must check `schema` and
`schema_version`, validate the fields they use, and ignore unknown fields. A
removal, type change or change of meaning in this summary requires a new report
schema version and an upgrade guide. Older files that lack a required summary
field must be rejected by that consumer rather than silently defaulted to zero.

Detailed entries, issue codes, reason/placement text, rule identifiers, controls,
source metadata and evidence dictionaries can change within v2. This also applies
to the other fields inside `profile` and `generator`. Pin the package revision
if you inspect those structures programmatically; use the summary for supported
automation. JSON key order and formatting are not part of the contract.

### Example: fail a local check when warnings are present

After generating the [synthetic demo](../examples/README.md), this check exits
zero for its clean report and nonzero if warnings are present or the expected
summary is unavailable. It does not print record details:

```python
import json
from pathlib import Path

report = json.loads(Path("pages/demo/view-report.json").read_text())
if (
    not isinstance(report, dict)
    or report.get("schema") != "glance-group-view-report"
    or type(report.get("schema_version")) is not int
    or report["schema_version"] != 2
):
    raise ValueError("Unsupported diagnostic report")
counts = report.get("counts")
warnings = counts.get("warning_issues") if isinstance(counts, dict) else None
if type(warnings) is not int or warnings < 0:
    raise ValueError("Missing or invalid warning count")
raise SystemExit(1 if warnings else 0)
```

This is a caller-defined quality gate, not a change to the render command's
exit-status semantics. A warning still needs interpretation using the detailed
diagnostics below.

## Example: a missing link does not exclude a published paper

Take the invented paper `DEMO-2099-01` from the synthetic fixture and give it a
`relatedAnalysis` link to `ANA-DEMO-2099-99`, which is absent from that snapshot.
The paper still has its own DEMO affiliation, publication date and DOI.

This shortened excerpt from its generated diagnostic entry shows the result
(unrelated fields and issue details are omitted):

```json
{
  "resource": "papers",
  "reference": "DEMO-2099-01",
  "state": "published",
  "placement": "Included in publication archive",
  "issues": [
    {
      "code": "missing_analysis",
      "level": "warning",
      "reason": "unresolved relatedAnalysis"
    }
  ]
}
```

Read `placement` first to see the actual page result. Then read the issue:
linked-analysis metadata is unavailable, but the paper's own fields still
support inclusion. Check the source relationship or snapshot completeness;
do not infer that the paper is unpublished or should be removed.

In this example, `counts.records_with_diagnostics` and `counts.warning_issues`
are both 1. The archive still contains all twelve synthetic publications.
