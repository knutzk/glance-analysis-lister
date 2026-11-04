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
