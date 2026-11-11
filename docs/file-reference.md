<!-- SPDX-FileCopyrightText: 2024-2026 Knut Zoch -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Saved data and generated files

A saved API snapshot lets you rebuild the curated registry without downloading
again. The registry, in turn, lets you regenerate pages without repeating
curation. Rendering also writes a diagnostic report to explain the result.
Keep these inputs and reports privately; publish only the intended pages and assets.

The [data guide](data.md) explains this workflow. This reference describes the
stored values, output names and URL parameters when you need to inspect a file
or connect the package to another tool.

## What each file is for

| File | Purpose |
| --- | --- |
| `glance_api_registry.json` | Source records saved by `download-api`; input to `build-registry`. |
| `glance_curated_registry.json` | Validated, enriched records from `build-registry`; input to rendering and Python preparation. |
| `ongoing.md` | Ongoing-analysis cards from `render-group`. |
| `papers.md`, `confnotes.md`, `pubnotes.md` | Separate publication tables from `render-group`. |
| `assets/gal-*.css`, `assets/gal-*.js` | Presentation and controls generated with the pages. The four asset pairs are `common`, `ongoing`, `papers` and `notes`. |
| `view-report.json` | Private counts, input fingerprints and explanations from `render-group`. |

The JSON filenames are defaults; commands accept explicit paths. HTML downloads
produce separate CSV exports, which cannot be used to build a registry. Site
configuration and the HTML build remain the consuming website's responsibility.
Install the generated pages and assets together. Existing output names and URL
meanings follow the [compatibility policy](upgrading.md#what-can-change); new files
may be added. HTML structure, CSS classes and JavaScript internals are not APIs.

## Read a curated registry

The registry contains `analyses`, `papers`, `confnotes` and `pubnotes` arrays,
plus matching nonnegative integer `counts`. All four arrays are required; empty
arrays with zero counts are valid storage. Download completeness and count-drop
protection are separate checks.

The bundled [JSON Schema](../analysis_lister/registry/schemas/curated.schema.json)
defines the retained fields and their types. Use `CuratedRegistry.from_json(path)`
to validate and read a file, or `validate_registry(data)` to validate a decoded
object. Both check nested types, dates, counts and identifier uniqueness. Reading
returns copies without adding defaults, enriching records, filtering by group or
making network requests. The [Python guide](python-access.md) shows both uses.

### Identity and relationships

Analyses and papers use `referenceCode`; notes use `temporaryReferenceCode`.
These native identifiers are nonempty and unique within each resource. Public
labels such as `finalReferenceCode` and `gal_finalReferenceCode` do not replace
them. Array order is preserved, but identify records by ID rather than position.

`relatedAnalysis` is an object or null. `relatedPublications` and note
`supersededBy` are arrays of objects or null. Their `type` and `referenceCode`
retain source evidence, including missing/null values. A relationship does not
merge records, imply a reciprocal link or guarantee that the target is present.
The reader's `resolve_link` accepts a known type and nonempty native reference,
returns `None` for an absent target and rejects unsupported link types.

### Missing values, people and dates

| Stored value | How to interpret it |
| --- | --- |
| Missing key | Information was not retained or supplied. |
| `null` | An explicitly absent value. |
| Empty list | No entries in the supplied collection. |
| Empty date string | No date supplied; not evidence that an event did not happen. |

Optional phase, metadata and documentation objects can be null. Required
`gal_analysisContacts` and `gal_contactEditors` are name arrays. Optional board,
reader and sign-off roles accept a string, string array or null; the writer emits
arrays for boards and readers. Optional derived metadata lists also accept null.
Raw `analysisTeam` is prohibited. People describe snapshot membership, not a
reconstructed historical membership.

Milestones retain calendar dates (`YYYY-MM-DD`) or RFC 3339 timestamps with a
timezone. Derived `gal_*MeetingDates` contain calendar dates only. Validation
checks that dates exist, but does not reorder milestones or infer missing events.
`fetched_at` is an optional source timestamp or null; `gal_curation.built_at`
records curation time and `contacts_as_of` the date used for current contacts.
These are separate from milestone dates. Readers preserve timezones as stored.

Titles, statuses, journal codes and collision metadata retain source wording,
including numeric-looking strings and units. DOI, URL and citation values stay
together in each `gal_dois` entry. `gal_publicationProvenance` records identifier
evidence; neither it nor URL validation establishes that a linked page is reachable.

### Current format rules

The registry has `schema: "glance-curated-registry"` and integer
`schema_version: 2`, independent of the package version. Only v2 is accepted;
valid saved v2 files need no rewriting. Changing the number by hand is not a
migration.

Optional additions and unknown fields, including nested fields, are accepted.
Status, journal and group codes remain open strings. Removing or renaming a field,
narrowing its type, making it required or changing its meaning requires a new
schema version. Changes to record retention also require compatibility review.
Fields do not disappear merely because a view stops using them.

A future breaking format must define supported inputs and tested migrations
without inventing missing history. Frozen synthetic fixtures remain readable;
new features receive additional fixtures. These are the current rules, separate
from package-release numbering.

The schema ships in the wheel and source archive. To inspect it programmatically:

```python
from importlib.resources import files

schema_text = (
    files("analysis_lister.registry")
    .joinpath("schemas/curated.schema.json")
    .read_text(encoding="utf-8")
)
```

External validators must enable `date` and `date-time` format checks. The package
uses JSON Schema Draft 2020-12 with `jsonschema.FormatChecker` and
`rfc3339-validator`, then checks counts and unique IDs in Python. A malformed
known field fails with its path; dangling links and contradictory chronology
are not structural errors.

## Link to generated records

Copy links from the generated pages where possible. The consuming site determines
the origin, directory prefix and Markdown-to-URL conversion; Zensical normally
serves `papers.md` at `papers/`. Site moves need redirects managed by that site.

Record fragments depend on the group and native identifier, not the title,
public display label or row order. The synthetic demo emits:

| Page | Fragment |
| --- | --- |
| Ongoing | `#analysis-demo-ana-demo-2099-01` |
| Papers | `#publication-papers-demo-demo-2099-01` |
| CONF notes | `#confnote-demo-conf-demo-2099-01` |
| PUB notes | `#pubnote-demo-pub-demo-2099-01` |

The form combines the page prefix with the lowercased group and native reference.
Runs outside `a-z`, `0-9` and `-` become `-`; edge hyphens are trimmed from the
combined group/reference part. Control, heading and detail-panel IDs are internal.

A fragment remains stable while that group and record remain on the page. Changes
to source data or selection can remove it; there is no historical-record redirect.
An ongoing permalink reveals and expands its card through active filters.
Publication links identify rows without overriding filters or expanding details.

### Filter parameters

| Pages | Parameter | Meaning and default |
| --- | --- | --- |
| All | `q` | Case-insensitive substring search; omitted means unrestricted. |
| Ongoing | `subgroup` | Exact subgroup name; repeat for OR selection. Omitted means all. |
| Ongoing | `sort` | `stage-desc` (default), `stage-asc` or `reference`. |
| Papers and notes | `after`, `before` | Inclusive `YYYY-MM` bounds. Undated rows satisfy After but not Before. |
| Papers | `status` | `published` (DOI present) or `under-review` (no DOI); repeat for OR selection. Omitted means both. |
| Notes | `supersession` | `non-superseded` (default), `superseded` or `all`. |

Use URL encoding, and never split subgroup names at commas. Different categories
combine with AND. Reloading and browser history restore the controls. A saved
link preserves filter choices, not a fixed result set.

Controls can trim search text, omit defaults and reorder parameters. Unknown
filter values are unsupported. Other application parameters and the fragment
survive updates and Reset. The listed names are reserved; the retired `subgroup`
parameter on note pages is removed during normalisation. See the
[page guide](pages.md) for examples of sharing views.

## Inspect a diagnostic report

Read reports to understand a render, or use their summary for a local quality
check. A successful render can contain warnings and still exit zero. Counts
precede browser filtering; analysis and diagnostic categories can overlap.

| Summary field | Meaning |
| --- | --- |
| `schema`, `schema_version` | `"glance-group-view-report"` and integer `2`. |
| `snapshot.filename`, `snapshot.sha256` | Input basename and SHA-256 of its exact bytes. |
| `profile.group`, `profile_sha256` | Selected main group and hash of the effective profile. |
| `generator.name` | `"glance-analysis-lister"`. |
| `generator.git_commit`, `generator.content_sha256` | Source revision and content hash. |
| `counts.ongoing_analyses`, `counts.analyses_needing_review` | Displayed analyses and analyses needing classification review. |
| `counts.publication_records` | Selected publications, including those not ready for the archive. |
| `counts.archive_publications` | Submitted/published papers and released notes, including superseded notes hidden by default. |
| `counts.records_with_diagnostics` | Distinct records with reported issues. |
| `counts.warning_issues`, `counts.informational_issues` | Numbers of issues, not records. |

All counts are nonnegative integers; hashes are 64 lowercase hexadecimal
characters. Within report v2, these summary names, types and meanings are stable;
additions are allowed at every level. Consumers must check the schema/version,
validate fields they use and ignore unknown fields. Reject a missing required
summary field rather than defaulting it to zero. Removing or changing a summary
field requires a new report version and upgrade guidance.

Detailed issues, rule traces, reason strings and other fields inside `profile`
or `generator` can change within v2. Pin the package revision if reading them
programmatically. JSON formatting and key order are not contractual. The
[warnings guide](problems.md) explains how to interpret the evidence.

### Trace the inputs and code

Markdown comments record the source revision, registry basename and hash,
profile hash and generator content hash; YAML front matter stays first. Assets
record the revision and retain their SPDX notices. These notices do not relicense
registry content. No generation timestamp is added.

The profile hash covers the group, title and selected policy, excluding unrelated
TOML groups, comments and formatting. The generator hash covers package Python
files and browser assets by relative name and content; matching checkouts and
installed packages produce the same content hash. Dictionary inputs are covered
by the snapshot and its curation provenance, since rendering does not reread them.

Modified checkouts carry `-dirty`; archives and wheels retain the revision at
build time, or `unknown` if unavailable. Content hashes distinguish changes even
when the revision label is the same. For comparing two renders, see
[tracing output](data.md#trace-your-output).
