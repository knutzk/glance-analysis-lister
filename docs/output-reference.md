# Generated files, URLs and report reference

[Documentation overview](README.md)

This page defines the output surfaces that integrations may depend on. Start
with the user guides to generate a website or investigate a warning; use this
reference when writing automation, preserving links or comparing output.

[Website integration](website.md) · [Warnings and recovery](problems.md) · [Compatibility](compatibility.md)

## Generated file and URL contract

The supported output names are:

| Output | Purpose |
| --- | --- |
| `ongoing.md` | Ongoing-analysis cards. |
| `papers.md`, `confnotes.md`, `pubnotes.md` | Separate publication tables. |
| `assets/gal-common.css`, `assets/gal-common.js` | Shared presentation and controls. |
| `assets/gal-ongoing.css`, `assets/gal-ongoing.js` | Analysis-card presentation and controls. |
| `assets/gal-papers.css`, `assets/gal-papers.js` | Paper-table presentation and controls. |
| `assets/gal-notes.css`, `assets/gal-notes.js` | CONF/PUB-note presentation and controls. |
| `view-report.json` | Private diagnostic report with a [supported summary](#supported-report-summary). |

New files may be added. Existing names and the URL forms below are compatibility
surfaces; changes must follow the [change policy](compatibility.md#change-and-deprecation-policy).
Generate and install pages and assets together. HTML layout, CSS class names,
internal element IDs and JavaScript functions are not extension APIs.

The consuming site owns the origin, group-directory prefix and conversion of
Markdown paths to URLs. For example, Zensical normally serves `papers.md` at
`papers/`. Moving the site or changing its URL style requires redirects in that
site; the renderer does not manage them.

### Record fragments

The record's group and native identifier determine its fragment. Titles,
publication display labels and row order do not. For the DEMO fixture:

| Page | Fragment |
| --- | --- |
| Ongoing | `#analysis-demo-ana-demo-2099-01` |
| Papers | `#publication-papers-demo-demo-2099-01` |
| CONF notes | `#confnote-demo-conf-demo-2099-01` |
| PUB notes | `#pubnote-demo-pub-demo-2099-01` |

These emitted record fragments are supported. The current form combines the
page-specific prefix with the group and native reference in lowercase, replacing
runs outside `a-z`, `0-9` and `-` with `-` and trimming edge hyphens from that
combined group/reference part. Prefer copying an emitted fragment to constructing
one. IDs for controls, headings and detail panels are internal.

The fragment stays the same while the group and native identifier stay the same
and the record remains on that page. A source change, lifecycle transition or
policy edit can remove the record from the page; there is no historical-record
redirect. An ongoing-card permalink reveals and expands its card even when
filters would hide it. Publication fragments identify rows but do not override
filters or expand details; include the appropriate filters when sharing them.

### Filter parameters

Use normal URL encoding for values, including spaces and commas. Repeat a
parameter to select several values where the table permits it; do not split a
subgroup name at commas.

| Pages | Parameter | Values and default |
| --- | --- | --- |
| All four | `q` | Case-insensitive substring search; omitted means no search restriction. |
| Ongoing | `subgroup` | Exact subgroup name, repeated for OR selection. Omitted means all subgroups. |
| Ongoing | `sort` | `stage-desc` (default), `stage-asc`, or `reference`. |
| Papers and notes | `after`, `before` | Inclusive `YYYY-MM` bounds. Omitted means no bound. Undated rows satisfy After but not Before. |
| Papers | `status` | `published` or `under-review`, repeated for OR selection. Omitted means both. These mean DOI present or absent. |
| Notes | `supersession` | `non-superseded` (default), `superseded`, or `all`. |

Controls restore these values when opening or reloading a link and on browser
history navigation. Filters from different categories combine with AND. A link
preserves selection intent, not a fixed set of results: the snapshot and policy
still determine the available records and subgroup choices.

Controls may normalise a URL by trimming search text, removing empty/default
values, or reordering parameters. Unknown filter values are not part of this
contract. Other application parameters and the fragment survive updates and
Reset. The names in this table are reserved for the package; `subgroup` on note
pages is a retired control and is removed when the URL is normalised.

See [ongoing links](pages.md#share-an-analysis-view) and
[publication links](pages.md#share-a-publication-view) for examples.

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

report = json.loads(Path("examples/demo/work/pages/view-report.json").read_text())
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
exit-status semantics. A warning still needs interpretation using the [warnings guide](problems.md).

## Generated headers

Markdown comments record the generator Git commit, registry filename and SHA-256,
and hashes of the effective profile and generator contents. YAML front matter
stays first. Copied CSS and JavaScript record the source commit and retain their
SPDX notices; those assets are independent of the registry.

A modified checkout is marked `-dirty`. Source archives and wheels retain the
revision recorded at build time; unavailable revisions are labelled `unknown`.
No generation timestamp is added. These notices do not apply the package licence
to registry content.

## Profile and generator hashes

The report's `profile` contains the group, display title and selected publication
policy. Its canonical `profile_sha256` excludes unrelated TOML groups, comments
and formatting.

`generator.content_sha256` hashes package Python files and browser assets by
relative name and content. It distinguishes local edits even when both builds
have the same `-dirty` commit label. Installed packages and checkouts with
identical contents have the same content hash.

Citation and identifier data are covered by the snapshot hash and its
[curation provenance](data.md); rendering does not reload those dictionaries.
Registry construction records identifier evidence, dictionary hashes and build
metadata.
