# GLANCE analysis lister

Download ATLAS GLANCE records, build a curated JSON registry, and generate
searchable group-wide analysis and publication pages. Rendering uses saved data
and requires no database, authentication, or live requests.

## Install

Use Python 3.13 or newer. From a checkout, create an environment and install the
package:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Live GLANCE downloads require an authorised CERN account.

The CLI is available as `analysis-lister` or `python -m analysis_lister`.

| Command | Purpose |
| --- | --- |
| `download-html` | Optional fallback: export all four HTML tables as independent CSVs. |
| `download-api` | Download all accessible analyses, papers, CONF notes and PUB notes through stare. |
| `compare-snapshots` | Compare two saved API snapshots or two curated registries offline. |
| `build-registry` | Curate saved API JSON using bundled public identifiers and citation metadata. |
| `render-group` | Generate ongoing-analysis, paper, CONF-note and PUB-note pages. |
| `resolve-dois` | Infer citations or retrieve public citation metadata from INSPIRE. |
| `format-citations` | Normalise cached non-manual citations offline. |

Use `COMMAND --help` for the complete argument list. Common options include
`--verbose`, `--quiet`, and `--color auto|always|never`. Diagnostics go to stderr;
results and output paths go to stdout. Missing publication-policy warnings also
go to stdout.

Downloads and builds log their configuration, input/output paths and processing
stages to stderr. API progress includes sorting, page counts and page timings;
build progress includes resource counts and identifier/DOI summaries. `--verbose`
adds each request's offset and limit; `--quiet` retains warnings and final results.
Credentials, authentication URL parameters and raw record payloads are not logged;
warnings may identify records needing attention.

## Download and build a registry

Run these commands **sequentially** from the directory that will hold your data:

```bash
analysis-lister download-api --login
analysis-lister build-registry
```

The API download retrieves all accessible records without group or subgroup filters.
Group selection happens when views are prepared.

| Data | Default location |
| --- | --- |
| Validated API source | `glance_api_registry.json` |
| Curated registry | `glance_curated_registry.json` |
| Shared citation dictionary | glance-analysis-lister’s maintained `json/doi_metadata.json` |
| Public PUB-note identifiers | Shared `json/pubnote_identifiers.json` |

API JSON and curated JSON default to the current working directory. Keep these
local artifacts out of version control in the consuming repository. The shared
citation dictionary is maintained with the package. A suitable
`.gitignore` block is:

```gitignore
/glance_api_registry.json
/glance_curated_registry.json
```

Set explicit destinations with:

```bash
analysis-lister download-api --output data/api.json
analysis-lister build-registry \
  --api-snapshot data/api.json \
  --output data/curated.json
```

Authentication uses stare's browser SSO and credential storage. Omit `--login`
to reuse stored credentials. Registry construction is offline: it needs only the
API JSON and bundled identifier/citation dictionaries. Keep downloaded records
and view reports out of the public package repository.

The API download stores validated stare model output, including explicit
relationships between independent records. `download-api --page-size 250` changes
how many records are requested per page; the default is 500. Performance depends
on server and network conditions. Any positive integer can be
requested, subject to server support; 500 is not a documented server maximum.
The selected page size is recorded in the source metadata. Retrieval remains sequential, through
one shared stare client, with response caching disabled.

Pages explicitly request ascending identifier sorting: `referenceCode` for
analyses/papers and `temporaryReferenceCode` for CONF/PUB notes. These aliases
are present on stare's detailed models, and its [sorting documentation](https://github.com/kratsg/stare/blob/d47df314e4e4bb00e34d00b1f8cbe3ce85bdf22c/docs/examples.md)
accepts camelCase API fields. Sorting is recorded in the snapshot metadata.
It does not create a transactional snapshot: records may still change between
requests. Duplicate detection, consistent totals, count-drop protection and atomic
publication protect the downloaded data. Offline tests exercise the actual stare client and
serializers, but cannot establish server limits, live sorting behavior or speed.

API downloads and registry builds reject per-resource count drops greater than
20%. `--allow-count-drop` overrides only that guard, never schema validation.
Inputs cannot be overwritten by registry output, and successful candidates are
published atomically. Run downloading and building sequentially against a given
set of files.

### Compare saved snapshots

Keep the previous snapshot under a separate filename before downloading or
building its replacement, then compare records offline:

```bash
analysis-lister compare-snapshots previous.json glance_curated_registry.json --details \
  --output snapshot-comparison.json
```

Compare two API files or two curated files from the same endpoint. Records are
matched by native identifier, independently of their order in the file. The
summary counts added, removed, changed and unchanged records for each resource.
`--details` lists affected identifiers and field paths; the optional JSON report
includes before/after values and input file hashes. Changes to statuses,
affiliations, DOIs, relationships and missing fields are all included. Reports
contain snapshot data and should remain private alongside the source files.

Container timestamps and build metadata are excluded from change detection.
Dictionary order is ignored, but list order is significant, including DOI and
correction order. Missing fields and explicit `null` values are distinct. A
change in the curation implementation or shared dictionaries can change a curated
record without a GLANCE edit; compare API snapshots to isolate upstream changes.
Neither input is modified. A successful comparison exits with status zero even
when differences are found; invalid snapshots or incompatible formats fail.

### Optional HTML fallback

Install the optional dependencies with `python -m pip install '.[html]'` from a
checkout, then run `analysis-lister download-html --login`. Chrome opens for
manual CERN SSO; later runs reuse `cookies.json`. This exports all available
columns from analyses, papers, CONF notes and PUB notes to the current directory.
Use `--csv-dir DIR` to choose another destination. These CSVs are standalone
exports, not inputs to `build-registry`.

TLS verification stays enabled, including support for `REQUESTS_CA_BUNDLE`.
Complete-table counters and identifiers are checked before batch publication;
failed writes roll back, retaining backups and an interruption marker if rollback
fails. Do not consume a batch while `.html-download-in-progress` exists. A
successful rerun repairs an interrupted batch. Keep cookies and exported data
private. `download-html --help` also describes saving and replaying HTML offline.

### Curated data and provenance

The curated registry retains independent API records and explicit relationships.
Selected nested collections become names or string lists. Added or reshaped
fields use the `gal_` prefix; source keys are removed only after enrichment.
The registry records identifier-source evidence, dictionary hashes and build
provenance. DOI/citation pairs, including corrections, stay aligned.

Transformation rules live in `registry/enrichment.py`: `STRING_LIST_FIELDS`
controls named-object conversions. After enrichment, `registry/fields.py` selects
only record fields
consumed by the views (including search, curation and diagnostics), down to nested
links, metadata and DOI/citation entries. New API fields are excluded by default.
Add fields to this selection when a view starts consuming them. The full API
snapshot remains the source for rebuilding; the curated file is not a lossless
API archive. Snapshot and build metadata are retained for provenance and safe
replacement. The curated schema is version 2.

`build-registry` logs retained/discarded field counts for each resource and the
input/output file sizes with their percentage change. Field counts refer to
nested object-key occurrences after enrichment, including original and derived
fields; they are not a measure of lost information. All records are retained.
Byte sizes include JSON formatting and build metadata.

### Public links and note identifiers

Paper public-page URLs are constructed from their native reference codes for
published or arXiv-submitted records. The canonical URL is recorded as derived;
page availability is not checked.

A valid API final identifier takes precedence. Otherwise, CONF/PUB public numbers
are extracted unambiguously from API public-page URLs. PUB notes whose API links
point to CDS use the shared `json/pubnote_identifiers.json` dictionary: public CDS
record number → public PUB identifier and canonical CDS source URL. Its initial
associations were retained from the existing GLANCE export; no CDS requests are
made at runtime. No private analysis identifiers, titles or people are stored in
this dictionary. It supplies static associations for historical detector and
technical PUB-note series, without a runtime updater.

Notes with release evidence but no identifier produce explicit diagnostics rather than
a guessed number. Each derivation is recorded in `gal_publicationProvenance`, and
the curated metadata records the dictionary hash and source counts.

## Configure and render group pages

The shared [`publication-curation.toml`](publication-curation.toml) defines publication
inclusion for all consumers and is bundled with the package. `render-group` uses
it automatically, regardless of the working directory. Edit this file to maintain
shared policies; use `--curation-config PATH` for an explicit alternative. For example:

```toml
[groups.TOPQ]
title = "Top Quark Physics"
groups = ["TOPQ"]
subgroups = []
keywords = []
```

Every criterion is combined with **OR**:

- A configured group matches an internal identifier token or a leading/additional
  main-group affiliation.
- A configured subgroup matches an exact leading/additional subgroup name.
- A configured keyword matches an exact label, ignoring case.

Missing publication affiliations or metadata can use the explicitly linked
analysis, with that derivation recorded in the view report. There is no implicit
extra group criterion. A policy with no criteria selects no publications.

Use one table per group, including groups using only their own name. `title`
sets publication-page headings. Missing group configuration prints a warning to
stdout and falls back to the internal identifier's group token.

```bash
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json \
  --output-dir docs/analyses
```

The default destination is `pages/group`. Output consists of `ongoing.md`,
`papers.md`, `confnotes.md`, `pubnotes.md`, `view-report.json`, and reusable assets.
`--group-title` changes the ongoing-page display title.

Generated Markdown comments identify the generator Git commit and the input
registry filename and SHA-256. YAML front matter remains first. Copied CSS and
JavaScript identify the source commit and preserve their SPDX notices; assets
are independent of the registry. A modified checkout is marked `-dirty`. Source
archives and wheels retain the revision recorded at build time. If revision
information is unavailable, the header explicitly says `unknown`. No generation
timestamp is added. These notices do not apply the package licence to registry
content.

Unchanged files are not rewritten, preserving their timestamps and inodes;
missing or modified generated files are replaced. Unrelated files remain
untouched. The log reports written/unchanged counts, which are not stored in the
report because they depend on the existing output directory.

The render command prints the `view-report.json` path to stdout; pages do not link
to this report. Diagnostics are grouped by cause: uncertain states, missing or
conflicting relationships, and missing public note identifiers. Each entry names
the record, states whether it is included on the page, and explains the issue's
effect on classification, progress, affiliations or identifiers. These effects
are separate from actual inclusion: a missing analysis link need not exclude an
otherwise published paper.

One-way publication links are informational because the outbound link is used
successfully. Other diagnostic causes remain warnings. Missing optional display
fields are not warnings. `--quiet` suppresses informational log messages; the JSON
report still retains them.

The report provides `diagnostic_groups` with issue counts, distinct-record counts
and affected entries. `warning_issues` and `informational_issues` count issues,
whereas `records_with_diagnostics` counts records once, including informational
cases. The existing `analyses_needing_review` and `records_with_diagnostics` lists
remain available and may overlap. The report also records the input hash, source
timestamps, policy, rule identifiers and detailed derivation evidence. It includes
selected records and their explicit one-hop relationship context; treat it as
private data alongside the generated pages.

### Ongoing analyses

Ongoing selection uses leading or additional main-group affiliation, independently
of publication-curation policy. Each native analysis appears once. Analyses with finished phase 0 and a linked
publication marked Created remain ongoing as “Awaiting publication review”;
unresolved linked publication states still require review. Closed and
completed analyses are excluded; uncertain records are listed separately.

Cards show GLANCE links, affiliations and review milestones. Expand a card for
people, supporting documents and metadata. The controls provide free-text search,
subgroup buttons, review-stage sorting, Expand all and Reset. Search includes
identifiers, titles, people, keywords, triggers and statistical tools. Review-stage
sorting follows the displayed milestone ticks.

Subgroup buttons are derived from recorded names in the group's namespace and
appear only when they have matching ongoing analyses. Repeated `subgroup` URL
parameters preselect buttons with OR logic:

```text
ongoing/?subgroup=DEMO-First&subgroup=DEMO-Second
```

Each card also has a permalink that reveals and opens it.

### Publication tables

Each publication type has its own expandable table, with one row per publication
and no pagination. Papers show GLANCE, arXiv and citation/DOI links and publication
dates. Notes show their public identifier, GLANCE and CDS links, and release dates.
Expanded details include recorded affiliations, people, metadata and supporting
links. Expand all and Collapse all apply to visible results.

All three pages search identifiers, subgroup names, titles, citations, keywords
and people. Papers also search DOI strings; notes search CDS URLs. Papers offer
Published (has a DOI) and Under review (no DOI) buttons. Notes offer non-superseded
and superseded buttons, defaulting to non-superseded notes; explicit superseding
objects are linked in the details.

After/before filters select inclusive year-and-month bounds on publication or
release dates. Undated entries remain visible unless a before bound is set.
Search, dates and status must all match; multiple selected statuses use OR.
Reset clears filters and restores the default status selection.

Publication URLs preserve `q`, `after`, `before`, paper `status` and note
`supersession` parameters, for example:

```text
papers/?q=example&after=2022-01&before=2024-06&status=published
```

### Enable browser assets

For output under `docs/analyses`, append these entries to the site's
configuration. Load the common files before the view-specific files:

```yaml
extra_css:
  - analyses/assets/gal-common.css
  - analyses/assets/gal-ongoing.css
  - analyses/assets/gal-papers.css
  - analyses/assets/gal-notes.css
extra_javascript:
  - analyses/assets/gal-common.js
  - analyses/assets/gal-ongoing.js
  - analyses/assets/gal-papers.js
  - analyses/assets/gal-notes.js
```

One copy serves all groups. The assets support Zensical instant navigation,
keyboard controls and dynamically inserted content. Without JavaScript, the full
collections and details remain readable. Browser filtering makes no live requests.

## Citations

`json/doi_metadata.json` is the maintained citation dictionary, also bundled with
the package. CLI commands use this shared dictionary by default, independently
of the current working directory. Citation resolution and formatting update the
selected dictionary; they do not create a per-consumer copy. `--doi-cache PATH`
selects another store; a missing custom store starts empty.

Resolve DOIs from a saved API or curated registry:

```bash
analysis-lister resolve-dois --snapshot glance_api_registry.json --method infer
analysis-lister resolve-dois --snapshot glance_api_registry.json --method inspire
```

`infer` is offline and recognises fully specified JHEP citations. `inspire` queries
public INSPIRE metadata. `auto` tries inference first. Repeated `--doi` arguments
can be used instead of a snapshot. `--limit 10` limits attempts;
`--refresh-existing` revisits non-manual entries. Entries whose source is `manual`
are protected from automatic replacement.

Publication DOIs are extracted from URL fields in the API's final journal
publication links. DOI resolver URLs and publisher URLs containing a DOI are
supported. Link labels are ignored; a DOI appearing only in a label is not used.
Publisher identifiers such as ScienceDirect PIIs are not converted into DOIs.

Resolved entries include citation text and provenance, with material labels when
known. A uniquely identified original publication is listed before its known
errata, addenda and editorial notes. Corrections are ordered by DOI-encoded dates
when those establish an order; otherwise their relative input order is retained.
Ambiguous ordering that cannot identify an original publication through material
labels or dates produces a warning. Ambiguous associations remain unresolved and retryable. Requests use a
separate session without GLANCE credentials, verified TLS, bounded retries and
rate limiting. Successful results are saved atomically after each entry.

Normalise non-manual cached journal names and starting pages offline with:

```bash
analysis-lister format-citations
```

After editing or resolving citations, run `build-registry` again to embed them,
then `render-group`. Citation resolution does not rewrite registry snapshots.
Run operations that write the same dictionary sequentially.

## Python access

Read a registry without importing downloaders, authentication clients or renderers:

```python
from analysis_lister.registry import CuratedRegistry

registry = CuratedRegistry.from_json("examples/synthetic_registry.json")
for paper in registry.records("papers"):
    print(paper["referenceCode"])
```

`get(resource, reference)` looks up a native identifier; `resolve_link(link)`
follows an explicit relationship. Returned records and metadata are copies.

Prepared collections are independent of Markdown:

```python
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

policy = PublicationPolicy(groups=("DEMO",))
view = prepare_group(registry, GroupProfile("DEMO", publication_policy=policy))
for publication in view.archive:
    for link in publication.details.publication_records:
        print(publication.label, link.label, link.url)
```

Prepared rows expose `metadata` containing search text and record attributes
such as keywords, triggers and subgroup assignments. `view.controls` separately
describes the available choices on each page: ongoing subgroup buttons and
sorting, paper publication status, and note supersession. Record metadata does
not imply that a corresponding filter control is displayed. The report records
these controls alongside the derivation evidence.

`load_publication_policy(path, group)` in `views.curation` loads the same TOML used
by the CLI. `None` denotes missing configuration; `PublicationPolicy()` is an
explicitly empty policy. Reports use schema version 2.

## Development and validation

From a checkout with an active environment:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
git diff --check
python -m build
```

The development requirements install the package in editable mode. Reinstall
after changing dependencies or package metadata. CI runs the offline checks on
Python 3.13 and validates the built wheel in a clean environment using
`scripts/check_distribution.py`. This checks the installed CLI, synthetic
rendering, packaged assets, shared dictionaries, publication policies and licences.

View tests are separated by preparation, ongoing rendering, paper rendering,
note rendering, shared publication controls, publication curation and output
building. Synthetic fixtures are shared through `tests/view_fixtures.py`.
`tests/test_retained_field_contract.py` guards source-record reads during
preparation and rendering: a lookup outside `registry/fields.py` fails with its
resource and nested path, even when the field is absent from the fixture. Tests
exercise populated and sparse records; add scenarios when introducing new
conditional view behavior. Output comparisons additionally check that trimming
records preserves rendering and search metadata.

Browser checks are separate developer tools. They require installed Chrome and
ChromeDriver, use shared synthetic fixtures, and clean up their temporary HTML,
screenshots and driver logs:

```bash
python tests/browser/check_ongoing.py --driver /path/to/chromedriver
python tests/browser/check_papers.py --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource confnotes --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource pubnotes --driver /path/to/chromedriver
```

Run the public synthetic example without credentials:

```bash
analysis-lister render-group --group DEMO \
  --snapshot examples/synthetic_registry.json --output-dir pages/demo
```

Tests use invented data and do not establish that live CERN authentication works.

## Package structure

| Directory | Responsibility |
| --- | --- |
| `downloaders/` | Independent API retrieval and optional HTML-to-CSV downloads, authentication, validation and safe publication. |
| `registry/` | Offline enrichment, schema validation, DOI extraction, snapshot comparison and thin registry access. |
| `citations/` | Citation storage, formatting, ordering, INSPIRE client and resolution workflow. |
| `views/` | Policies, prepared data, relationships, provenance reports, renderers and browser assets. |
| `tests/browser/` | Manual synthetic browser checks. |
| `scripts/` | Installed-distribution validation used by CI. |

Within `views/`, `analysis_states.py` and `publication_states.py` contain the
traceable lifecycle and milestone rules. Collection preparation uses these rules
without importing renderers. Markdown rendering consumes prepared records and
page controls; `people.py` shares plain-text board/chair formatting across views.
`diagnostics.py` classifies diagnostic causes and effects; `report.py` records
the corresponding decisions and evidence.

## Licence

Copyright © 2024–2026 Knut Zoch. Licensed under
[GNU GPL version 3](LICENCE), `GPL-3.0-only`.

Maintainer: [Knut Zoch](https://github.com/knutzk).
