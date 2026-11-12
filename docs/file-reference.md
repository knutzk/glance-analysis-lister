# Saved data and generated files

A saved API snapshot lets you rebuild the curated registry without downloading
again. The registry, in turn, lets you regenerate pages without repeating
curation. Rendering also writes a diagnostic report to explain the result.
Keep these inputs and reports privately; publish only the intended pages and assets.

The [data guide](data.md) explains this workflow. This reference describes the
stored values, output names and URL parameters when you need to inspect a file
or connect the package to another tool. Generated JSON supports the package's
own workflow; it is not a stable external interchange API. An upgrade may require
rebuilding generated data. Custom citation stores contain user-maintained work
and are handled separately in the [upgrade guide](upgrading.md#preserve-the-inputs).

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

The bundled [JSON Schema](../grove/registry/schemas/curated.schema.json)
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
timezone. Four paper `publicationPhase` fields also accept the API's local
minute-precision format (`YYYY-MM-DDTHH:MM`): `arXivSubmissionDate`,
`firstRefereeReportDate`, `firstProofDate` and `publishedOnlineDate`. These values
carry no timezone; none is inferred or added. Downloads through stare 0.7 use
this format and calendar-only meeting dates. Previously saved snapshots retain
their accepted date representations and do not need conversion.
Derived `gal_*MeetingDates` contain calendar dates only. Validation
checks that dates exist, but does not reorder milestones or infer missing events.
`fetched_at` is an optional source timestamp or null; `gal_curation.built_at`
records curation time and `contacts_as_of` the date used for current contacts.
These are separate from milestone dates. Readers preserve source precision and
timezones as stored.

Titles, statuses, journal codes and collision metadata retain source wording,
including numeric-looking strings and units. DOI, URL and citation values stay
together in each `gal_dois` entry. Papers also retain `fullTitle` and
`publicationPhase.finalTitleTex` for the copy-ready citation. Both are optional
strings or null; missing, null and empty values remain distinct in storage.
`gal_publicationProvenance` records identifier evidence; neither it nor URL
validation establishes that a linked page is reachable.

### Current format rules

The `schema` string identifies the file's purpose: `glance-api-registry` for
source snapshots and `glance-curated-registry` for curated data. There is no
package-specific JSON schema version number. Legacy `schema_version` fields
are ignored; rewriting a curated registry omits them.

Generated files include a top-level `generator` object:

| Field | Purpose |
| --- | --- |
| `name` | `glance-grove`. |
| `git_commit` | Source revision for tracing the generating code, or `unknown` if unavailable. |
| `content_sha256` | Fingerprint of package Python files, validation schemas and browser assets. |

When reading a snapshot, the package compares its fingerprint with the running
code. Different, missing or unrecognised generator metadata produces a warning
and execution continues if the data passes validation. Warnings go to stderr in
the CLI, including with `--quiet`; Python callers receive a logging warning.
Neither a different commit nor a different worktree path alone causes a warning
when the code contents match. Documentation-only changes do not change the hash.

This comparison detects different generating code; it does not prove that the
file is incompatible. Regenerate with the current package if problems occur.
Older or hand-authored files, including the synthetic demo, can lack metadata and
still be used. Custom citation stores are exempt from generator checks because
they contain user-maintained data.

Structural validation remains independent: the wrong file type, malformed known
fields, inconsistent counts or duplicate identities fail. Unknown additions are
accepted, and status, journal and group codes remain open strings. Retained fields
can evolve without a permanent external compatibility guarantee. If a saved
registry no longer validates, follow the
[rebuild guidance](upgrading.md#if-a-saved-file-is-no-longer-supported).

The schema ships in the wheel and source archive. To inspect it programmatically:

```python
from importlib.resources import files

schema_text = (
    files("grove.registry")
    .joinpath("schemas/curated.schema.json")
    .read_text(encoding="utf-8")
)
```

External validators must enable `date` and `date-time` format checks. The package
uses JSON Schema Draft 2020-12 with `jsonschema.FormatChecker` and
`rfc3339-validator`, then checks counts and unique IDs in Python. The four local
paper timestamps use a schema pattern that validates calendar dates and times;
no custom format checker is required. A malformed known field fails with its path;
dangling links and contradictory chronology are not structural errors.

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
| `schema` | `"glance-group-view-report"`. |
| `snapshot.filename`, `snapshot.sha256` | Input basename and SHA-256 of its exact bytes. |
| `profile.group`, `profile_sha256` | Selected main group and hash of the effective profile. |
| `generator.name` | `"glance-grove"`. |
| `generator.git_commit`, `generator.content_sha256` | Source revision and content hash. |
| `counts.ongoing_analyses`, `counts.analyses_needing_review` | Displayed analyses and analyses needing classification review. |
| `counts.publication_records` | Selected publications, including those not ready for the archive. |
| `counts.archive_publications` | Submitted/published papers and released notes, including superseded notes hidden by default. |
| `counts.records_with_diagnostics` | Distinct records with reported issues. |
| `counts.warning_issues`, `counts.informational_issues` | Numbers of issues, not records. |

All counts are nonnegative integers; hashes are 64 lowercase hexadecimal
characters. The table describes the report produced by the current package.
Summary fields, detailed issues and rule traces can change between releases;
the report is explanatory output, not a stable external JSON API. Its generator
metadata identifies the code that produced it, without promising field stability.

If you inspect reports in a script, pin the package version and check the fields
you use when upgrading. A missing warning count should not silently become zero.
Regenerate reports with the pages after an upgrade; there is no report migration
workflow. The [warnings guide](problems.md) explains how to interpret the evidence.

### Trace the inputs and code

Markdown comments record the source revision, registry basename and hash,
profile hash and generator content hash; YAML front matter stays first. Assets
record the revision and retain their SPDX notices. These notices do not relicense
registry content. No generation timestamp is added.

The profile hash covers the group, title and selected policy, excluding unrelated
TOML groups, comments and formatting. The generator hash covers package Python
files, validation schemas and browser assets by relative name and content; matching checkouts and
installed packages produce the same content hash. Dictionary inputs are covered
by the snapshot and its curation provenance, since rendering does not reread them.

Modified checkouts carry `-dirty`; archives and wheels retain the revision at
build time, or `unknown` if unavailable. Content hashes distinguish changes even
when the revision label is the same. For comparing two renders, see
[tracing output](data.md#trace-your-output).
