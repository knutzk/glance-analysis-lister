# Command-line reference

[Documentation index](README.md)

Run `analysis-lister COMMAND`, or `python -m analysis_lister COMMAND`.
This reference describes the current CLI; v1.0 compatibility promises are still
being defined. Use `analysis-lister COMMAND --help` to check your installed version.
For worked sequences, see [commands and recovery](workflows.md).

`analysis-lister --version` prints `analysis-lister VERSION` to stdout and exits
successfully without running a workflow. This top-level option reports installed
package metadata; `-v` remains the verbose-logging option.

## Paths and shared options

Relative paths resolve from the calling directory. Snapshot defaults are
`glance_api_registry.json` (API) and `glance_curated_registry.json` (curated).
Output parents are created as needed. Do not use an input path as an output
destination.

Two defaults are located through the package, independently of the working directory:

| Option | Default | Used by |
| --- | --- | --- |
| `--curation-config PATH` | Shared `publication-curation.toml` | `refresh`, `render-group` |
| `--doi-cache PATH` | Shared `json/doi_metadata.json` | `refresh`, `build-registry`, `resolve-dois`, `format-citations` |

These are checkout files for an editable installation, or installed data files
for a wheel. Citation commands **write to the selected store**, including the
shared default. A missing custom store starts empty. See
[citation maintenance](citations.md) and [policy fields](rendering.md#publication-policies).
Public-note identifiers are read from the packaged dictionary; there is no CLI
override for that dictionary.

Every command accepts these console options, before or after its name:

| Option | Default | Effect |
| --- | --- | --- |
| `-h`, `--help` | — | Show help and exit. |
| `-v`, `--verbose` | Off | Add detailed logs, timestamps and module names. |
| `-q`, `--quiet` | Off | Keep warnings, errors and final results. Mutually exclusive with verbose mode. |
| `--color auto\|always\|never` | `auto` | Control terminal colour; automatic mode respects `NO_COLOR`. |

Unless specified otherwise, optional switches are off and optional paths have
no value. `--allow-count-drop` on API download, build and refresh permits a
per-resource count reduction greater than 20%; other validation still applies.

## `refresh`

Download API data, build a curated registry and render groups, sequentially.
Requires CERN access. Completed stages remain if a later stage fails.

| Option | Default / requirement | Meaning |
| --- | --- | --- |
| `--groups GROUP [GROUP ...]` | Required | Unique uppercase group tokens, such as `TOPQ HIGP`. |
| `--api-snapshot PATH` | API snapshot default | Download destination, then build input. |
| `--snapshot PATH` | Curated snapshot default | Build destination, then render input. |
| `--output-dir DIR` | `pages` | One group writes here; multiple groups use lowercase subdirectories. |
| `--curation-config PATH` | Shared policy | Publication selection and titles. |
| `--doi-cache PATH` | Shared citation store | Citations to embed during the build; no citation-service requests. |
| `--login` | Off | Open browser SSO instead of reusing stored credentials. |
| `--page-size N` | `500` | Positive number of records requested per API page, subject to server support. |
| `--allow-count-drop` | Off | Override the count guard for download and build. |

## `download-api`

Download all accessible records for the four resources through stare. Requires
CERN access; selection by group happens during view preparation.

| Option | Default | Meaning |
| --- | --- | --- |
| `--output PATH` | API snapshot default | Validated API JSON destination. |
| `--login` | Off | Open browser SSO instead of reusing stored credentials. |
| `--page-size N` | `500` | Positive records per page, subject to server support. |
| `--allow-count-drop` | Off | Override the count guard against the existing destination. |

## `build-registry`

Curate a saved API snapshot offline. All records remain; only adopted fields
are retained and enriched. HTML CSV exports cannot be used as input.

| Option | Default | Meaning |
| --- | --- | --- |
| `--api-snapshot PATH` | API snapshot default | Saved API JSON input. |
| `--output PATH` | Curated snapshot default | Validated curated JSON destination. |
| `--doi-cache PATH` | Shared citation store | Citation metadata to embed. |
| `--allow-count-drop` | Off | Override the count guard against the existing destination. |

## `render-group`

Prepare views and render four pages, browser assets and `view-report.json` from
a saved curated registry. Runs offline; see [generated output](rendering.md).

| Option | Default / requirement | Meaning |
| --- | --- | --- |
| `--group GROUP` | Required | Exact main-group name for ongoing membership and the policy table to load. |
| `--snapshot PATH` | Curated snapshot default | Saved curated JSON input. |
| `--output-dir DIR` | `pages/group` | Destination for pages, assets and report. |
| `--curation-config PATH` | Shared policy | Publication selection and publication-page titles. |
| `--group-title TEXT` | Group name | Ongoing-page display title. |

## `compare-snapshots`

Compare saved data offline. Both inputs must have the same format (API or
curated) and endpoint. A successful comparison exits zero even if records changed.

| Argument / option | Default / requirement | Meaning |
| --- | --- | --- |
| `before` | Required positional path | Previous snapshot. |
| `after` | Required positional path | New snapshot. |
| `--details` | Off | List affected native identifiers and changed field paths. |
| `--output PATH` | No file written | Write a detailed JSON report, including before/after values. |

## `download-html`

Export four standalone CSV tables. Requires the `html` extra; live login also
requires Chrome. Uses separate credentials from the API client.

| Option | Default | Meaning |
| --- | --- | --- |
| `--csv-dir DIR` | Calling directory | CSV batch destination. |
| `--cookies PATH` | `cookies.json` | Read saved cookies, or save new cookies with `--login`. |
| `--login` | Off | Open Chrome for manual SSO. Mutually exclusive with `--from-html`. |
| `--from-html DIR` | Live retrieval | Replay saved HTML and its manifest offline; no credentials needed. |
| `--save-html DIR` | No saved HTML | Save downloaded HTML and its manifest for replay. |

`--from-html` and `--save-html` cannot be combined. Saved HTML and CSV outputs
must use separate directories. There is no HTML `--allow-count-drop` option;
the exporter validates table contents and publishes them as a batch. See
[HTML recovery](workflows.md#validation-and-recovery) before consuming an interrupted batch.

## `resolve-dois`

Update the citation store from individual DOIs or a saved snapshot. Choose
exactly one input form. Manual entries are never replaced automatically.

| Option | Default / requirement | Meaning |
| --- | --- | --- |
| `--snapshot PATH` | One input form required | Read DOIs from an API snapshot or curated registry. |
| `--doi DOI` | One input form required | Bare DOI or doi.org URL; repeat for multiple DOIs. |
| `--doi-cache PATH` | Shared citation store | Store to update; must not overwrite the snapshot. |
| `--method infer\|inspire\|auto` | `infer` | Offline JHEP inference, public INSPIRE lookup, or inference followed by lookup. |
| `--refresh-existing` | Off | Revisit existing non-manual entries. |
| `--limit N` | No limit | Positive maximum number of eligible entries to attempt. |

`inspire` and `auto` may access the public network; they do not use GLANCE
credentials. Successful resolutions are saved incrementally. Rebuild and render
afterwards to propagate citations to pages.

## `format-citations`

Normalise non-manual citations offline. The only command-specific option is
`--doi-cache PATH`, defaulting to the shared citation store. Updates that store;
snapshots and pages are unchanged until rebuilt and rendered.

## Exit status and logs

Successful commands and help exit `0`. Argument-parsing errors exit `2`.
Handled validation, filesystem and request failures exit `1`; inspect the error
and [troubleshooting guidance](troubleshooting.md) before retrying.

Results and output paths go to stdout, diagnostics to stderr. Missing-policy
warnings also go to stdout. See [logs and summaries](workflows.md#logs-and-summaries)
for verbosity and download-completion details.
