# Commands and recovery

[Documentation index](README.md)

Use `analysis-lister` or `python -m analysis_lister` after
[installation](../README.md#install-and-try-without-credentials). Live GLANCE
access requires an authorised CERN account. Run data commands from the directory
where you want to keep the snapshots, or supply explicit paths.

The [command-line reference](cli-reference.md) lists every command, option and
default. Use `analysis-lister COMMAND --help` for your installed version.

## Choose where to start

Reuse the earliest saved input needed for your change. Only downloading fresh
GLANCE records requires CERN access; rendering never refreshes the snapshot.

| What changed or needs doing | Start here | Then |
| --- | --- | --- |
| Get current GLANCE records and update group pages | [Refresh](#refresh-group-pages-in-one-command) | Inspect the report and integrate the pages into your site. |
| Rebuild after a curation-code or identifier-dictionary update | [Build from a saved API snapshot](#download-and-build-a-registry) | Render the resulting curated registry. |
| Update citations | [Maintain the citation store](citations.md) | Build with that store, then render. Only INSPIRE lookup needs public network access. |
| Change group, publication policy, titles or renderer | [Render a saved curated registry](#reuse-a-snapshot-offline) | Inspect the new pages and report. |
| Understand changes between saved snapshots | [Compare snapshots](#compare-saved-snapshots) | Review the summary and, if needed, the detailed report. |
| Inspect your group alongside the synthetic demo | [Local group preview](site.md#preview-your-group-alongside-demo) | Render to `pages/topq`, then explicitly select it in the local documentation preview. |
| Add generated pages to an existing site | [Stage pages and enable assets](rendering.md#integrate-into-a-consuming-site) | Build and preview the consuming site. |

## Refresh group pages in one command

From the repository that consumes the pages, run:

```bash
analysis-lister refresh --groups TOPQ --output-dir docs/analyses --login
```

Refresh downloads one API snapshot, builds the curated registry offline, then
renders the group pages. The stare client manages browser single sign-on (SSO),
credential storage and token refresh. Omit `--login` to reuse stored credentials.
Refresh does not download HTML or query citation services.

For several groups:

```bash
analysis-lister refresh --groups TOPQ HIGP --output-dir pages
```

A single group writes directly into the output directory. Multiple groups use
lowercase subdirectories, such as `pages/topq/` and `pages/higp/`. Group tokens
must be uppercase and unique.

Configuration and destination collisions are checked before authentication.
Stages run sequentially and stop at the first failure; completed outputs remain.
There is no rollback across the whole refresh or all rendered pages. The final
summary lists snapshot paths, group outputs, diagnostic reports, counts and
elapsed time. See [recovery](#validation-and-recovery) to resume a failed run.

## Download and build a registry

To run the stages separately, execute these commands **in order**:

```bash
analysis-lister download-api --login
analysis-lister build-registry
```

The download retrieves all accessible records, including their explicit
relationships. Group and subgroup selection happens later, when preparing views.
Building the registry needs only the saved API JSON and identifier/citation
dictionaries; it makes no network requests.

Default snapshot and dictionary locations are listed in the
[reference](cli-reference.md#paths-and-shared-options).

To choose snapshot destinations:

```bash
analysis-lister download-api --output data/api.json
analysis-lister build-registry \
  --api-snapshot data/api.json \
  --output data/curated.json
```

Keep real snapshots and diagnostic reports out of version control. Add these
entries to the consuming repository's `.gitignore`:

```gitignore
/glance_api_registry.json
/glance_curated_registry.json
**/view-report.json
```

Add any custom destinations too. Publish generated Markdown and assets only when
the records they expose are suitable for the intended audience.

### API pagination

`download-api --page-size 250` requests 250 records per page. Any positive integer
is accepted locally, subject to server support; the default of 500 is not a
known server maximum. Requests run sequentially through one stare client, with
response caching disabled. Speed depends on the server and network.

Pages request ascending native-identifier order: `referenceCode` for analyses
and papers, `temporaryReferenceCode` for notes. These are stare model aliases;
its [sorting documentation](https://github.com/kratsg/stare/blob/d47df314e4e4bb00e34d00b1f8cbe3ce85bdf22c/docs/examples.md)
accepts camelCase API fields. The snapshot records the requested sort and page size.

Records can change between requests, so this is not a transactional snapshot.
Duplicate detection, consistent totals, count-drop checks and atomic publication
protect the output. Offline tests exercise the stare client and serializers;
live server limits, sorting behaviour and speed need separate validation.

## Reuse a snapshot offline

If you already have a curated registry, render it directly. For example, from
this checkout, use the public fixture and its policy:

```bash
analysis-lister render-group --group DEMO \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/publication-curation.toml \
  --output-dir examples/demo/work/pages
```

This produces four ongoing analyses and twelve archived publications, with no
diagnostic warnings. Each note page initially hides one superseded note. Use the
[demo tutorial](../examples/README.md#tutorial-change-publication-selection) to
edit a policy copy and see which pages change.

For your own data, replace the snapshot, group and policy paths. `render-group`
handles one group per invocation; use separate output directories when rendering
several groups from the same snapshot. The group selects ongoing analyses by
their leading or additional main-group affiliation and identifies the policy
table used for publications. A publication policy can select other groups,
subgroups or keywords; it does not change ongoing-analysis membership.
Browser filters only narrow records already included in a generated page.

If curation rules or citation data changed, first rebuild from the saved API
snapshot, then render the new registry:

```bash
analysis-lister build-registry --api-snapshot data/api.json \
  --doi-cache data/doi-metadata.json --output data/curated.json
analysis-lister render-group --group TOPQ --snapshot data/curated.json \
  --curation-config publication-curation.toml --output-dir pages/topq
```

These paths assume you have saved the API snapshot and chosen your own policy
and [citation store](citations.md#choose-a-store). Run the commands in order and
continue only if the build succeeds. The synthetic fixture is already curated;
it is a rendering input, not an API input to `build-registry`.

## Compare saved snapshots

Save the previous snapshot under a separate filename before replacing it, then
compare the two files:

```bash
analysis-lister compare-snapshots previous.json glance_curated_registry.json --details \
  --output snapshot-comparison.json
```

Both inputs must be API snapshots or both must be curated registries, from the
same endpoint. Records are matched by native identifier regardless of file order.
The summary counts added, removed, changed and unchanged records per resource.
`--details` lists affected identifiers and field paths. The optional JSON report
also contains before/after values and file hashes; keep it private with the inputs.

Comparison includes statuses, affiliations, DOIs, relationships and missing
fields. It ignores container timestamps, build metadata and dictionary order.
List order matters, including DOI and correction order; missing fields differ
from explicit `null` values.

A curation-code or dictionary change can alter a curated record without a GLANCE
edit. Compare API snapshots to isolate upstream changes. Neither input is
modified. A valid comparison exits with status zero even when it finds changes;
invalid snapshots or incompatible formats fail.

## Optional HTML fallback

From a checkout, install the HTML dependencies and start the export:

```bash
python -m pip install '.[html]'
analysis-lister download-html --login
```

Chrome opens for manual CERN SSO. Later runs reuse `cookies.json`. The command
exports all available columns from the analyses, papers, CONF-note and PUB-note
tables to the calling directory. Use `--csv-dir DIR` for another destination.
These CSVs are standalone exports; `build-registry` does not read them.

TLS verification remains enabled and supports `REQUESTS_CA_BUNDLE`. Table counts
and identifiers are checked before all four files are published as a batch.
Duplicate or unnamed non-identifier headers receive unique names; every column
and its original position are retained. `download-html --help` describes how to
save HTML and replay it offline.

Keep cookies and exports private. Ignore `cookies.json`, the four CSVs,
`html_manifest.json`, `.html-download-in-progress`, `.refresh-*/` and any directory
selected with `--save-html`.

## Validation and recovery

API downloads and registry builds reject a per-resource count drop greater than
20%. Use `--allow-count-drop` only for an understood reduction; it does not bypass
schema validation. Validated JSON candidates replace the output atomically, and
registry output cannot overwrite its input. Run operations that write the same
files sequentially.

For symptoms and commands to resume at the failed stage, see
[troubleshooting](troubleshooting.md#resume-an-interrupted-workflow). Rendered
files are replaced individually. HTML publication uses batch rollback; retain
the reported backups and recovery paths if rollback fails, and do not consume
an export while `.html-download-in-progress` exists.

Download failures compare output bytes with their pre-download state before
claiming preservation. If the check fails or bytes changed, the command says so.
An HTML interruption marker takes precedence: the batch is reported as incomplete
and staging/recovery paths are listed. Debug HTML may be partial. Preserved bytes
do not prove that the pre-existing data was valid or complete.

## Logs and summaries

Diagnostics, including missing publication-policy warnings, go to stderr;
results and output paths go to stdout. Summaries
are flushed immediately to preserve order in combined redirected logs.

Downloads and builds log configuration, paths and processing stages. API progress
includes sorting, page counts and timings; build progress includes resource counts
and identifier/DOI summaries. `--verbose` adds request offsets and limits.
`--quiet` retains warnings and final results. `--color auto|always|never` controls
colour. Logs omit credentials, authentication URL parameters and raw records,
though warnings may name records that need attention.

Both download commands finish with paths, per-resource and total counts, elapsed
time including authentication and publication, and the checks that passed. API
count-drop overrides are stated explicitly. Offline HTML replay uses the same
summary without authentication or network access.
