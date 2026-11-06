# Troubleshooting

[Documentation index](README.md)

Start with the failing command and its error. Add `--verbose --color never` when
you need more detail. Errors go to stderr; see [logging](workflows.md#logs-and-summaries)
before redirecting output. Logs and reports may contain record identifiers, so
remove private information before sharing a reproducer.

## Installation and missing modules

| Symptom | Check and remedy |
| --- | --- |
| `analysis-lister` is not found | Activate the environment where you installed it, or use that environment's `python -m analysis_lister`. |
| A module such as `jsonschema` is missing | Use the same Python for installation and execution. From a checkout, `python -m pip install .` installs runtime dependencies. |
| Documentation preview lacks dependencies | Activate `.venv` and run `python -m pip install -r requirements-docs.txt`, then `python scripts/docs.py serve`. |
| HTML export reports missing optional dependencies | From a checkout, install `python -m pip install '.[html]'`. Browser login also needs Chrome. |

`python --version` should report the tested Python 3.13 environment.
`python -m pip check` identifies inconsistent installed dependencies. Development
and documentation dependencies are separate from an ordinary package install.

## Authentication and connectivity

API downloads and `refresh` use stare's credentials. If reuse fails, retry the
same command with `--login` and complete browser SSO using an account authorised
for GLANCE. HTML export has its own cookie file: `No cookies found` or
`Invalid or expired cookies` calls for `download-html --login`, with the same
`--cookies PATH` on subsequent runs. An API login does not refresh HTML cookies.

| Error | Next step |
| --- | --- |
| Authentication failed or HTTP 401 | Retry with `--login`. If it persists, check account access and authentication-service connectivity. |
| HTTP 403 | Check your account's GLANCE permissions. A new login does not grant missing access. |
| HTTP 404 | Check the configured endpoint and client/API compatibility. |
| HTTP 429 | Wait before retrying; the service is limiting request rate. |
| HTTP 5xx | Retry after the service recovers. |
| API network failure | Check connectivity, proxy and TLS/CA settings. This category can include timeouts; it does not imply expired credentials. |
| HTML connection failure or timeout | Check DNS, network/proxy settings and service availability before retrying. |
| API client configuration failure | Check stare settings and the installed dependencies. |

The downloader does not automatically retry these failures. Offline build and
render commands can continue using saved snapshots. API retrieval and HTML
transport errors omit upstream exception text, response bodies, URL credentials,
query strings and exception chains, including with `--verbose`. The API error
retains the exception type for diagnosis; an unknown retrieval failure should be
reported with that type and a synthetic reproducer.

For an HTML TLS error, check the server certificate chain and any configured
proxy or CA bundle. The exporter honours `REQUESTS_CA_BUNDLE` (or
`CURL_CA_BUNDLE`) and otherwise includes its bundled intermediate certificate.
An override must point to a trusted PEM bundle suitable for the connection.
Keep certificate and hostname verification enabled. The API client uses stare's
transport; the HTML certificate handling does not configure that client.

## Schema, counts and destination errors

| Symptom | Check and remedy |
| --- | --- |
| Expected a supported API or curated registry | Check which file you passed: `build-registry` reads API JSON; `render-group` reads curated v2 JSON. CSVs and diagnostic reports are neither. |
| A schema error names a field path | Inspect that field's type against the [curated contract](curated-format.md). Use a small invented reproducer when reporting it. Do not change a version number to force acceptance. |
| API response validation failed | The client could not parse a response or a record lacked its native identifier. Check client/API compatibility; the command does not skip malformed records or publish a partial snapshot. |
| A reader rejects an older or future schema version | Use a compatible package or rebuild from a supported saved API snapshot. There is currently no automatic schema migration. |
| Counts disagree, identifiers repeat or API pagination is incomplete | Treat the candidate as invalid. Pagination errors name the resource and reason: an empty/invalid count, changing total, incomplete page or duplicate. Check source completeness, then retry the complete download; `--allow-count-drop` cannot bypass these checks. |
| A resource count dropped by more than 20% | Compare the previous and candidate counts, account permissions and endpoint. Only retry with `--allow-count-drop` when the reduction is understood. |
| Endpoint differs from the existing destination | Use a new destination for a different source. Retain the previous snapshot for comparison. |
| An output would overwrite an input | Choose distinct paths for snapshots, dictionaries, policies and generated output. `refresh` checks these before authentication. |
| A policy is rejected | Check the [accepted fields and types](rendering.md#publication-policies). Every group table is validated, including groups not requested in this run. |

The count-drop guard compares with an existing destination. Writing to a new
path provides no historical baseline. Preserve the original files when
investigating a reduction; a successful schema check alone does not establish
download completeness.

## Resume an interrupted workflow

`refresh` stops at the first failed stage and retains completed stages. Inspect
its error and saved outputs, correct the cause, then restart at the failed stage.
The download and build each compare counts against their own existing destination;
a successful download can still be followed by a rejected build.

| Failure point | State to expect | Where to resume |
| --- | --- | --- |
| API pagination interrupted, or download count drop rejected | The API destination is not replaced; registry and pages are untouched. | Retry the download or `refresh` after resolving the cause. Pagination restarts from the beginning. |
| Registry validation/count check fails, or writing is interrupted before replacement | A completed API download remains available. The previous curated registry and pages remain. | `build-registry` using the saved API snapshot, then render. Pass `--allow-count-drop` to the build only if its reduction is understood. |
| Rendering fails partway through one group | Earlier groups remain complete; the failing group may mix old and new files; later groups are untouched. | Rerender the failing group and every later group, using the same saved registry and policy. |
| HTML CSV publication and rollback both fail | The interruption marker and reported recovery files remain; the destination is incomplete. | Preserve those files, fix the cause and rerun the full export, or replay a complete saved HTML set. |

For a successful download followed by a failed build:

```bash
analysis-lister build-registry --api-snapshot data/api.json --output data/curated.json
analysis-lister render-group --group TOPQ --snapshot data/curated.json \
  --output-dir docs/analyses
```

Substitute the paths, citation store and publication policy from your original
run. If only rendering failed, run just `render-group`. For several groups,
repeat it for each destination that still needs updating. These steps use saved
data and do not authenticate or download again.

JSON candidates are validated before atomic replacement. Rendered files are
replaced individually, so a failed render can leave a mixture of old and new
files; rerender the same destination after fixing the error. There is no
workflow-wide rollback. See [storage and recovery guarantees](workflows.md#validation-and-recovery)
for what a failure summary establishes about existing bytes.

For HTML export, `.html-download-in-progress` marks an incomplete batch. Do not
consume it while that marker exists. Preserve any reported backups and recovery
paths, especially if rollback failed. Correct the cause and rerun to the same
CSV destination; a successful run completes the batch. If you saved a complete
HTML set and manifest, you can recover offline:

```bash
analysis-lister download-html --from-html saved-html --csv-dir exports
```

Keep these directories separate. A partially saved HTML set is not sufficient
for replay. Do not delete the interruption marker to make an incomplete batch
appear complete.

These recovery paths have [synthetic failure-injection coverage](development.md#recovery-checks).
Handled exceptions and Ctrl+C can run cleanup; a force-killed process or power
loss cannot. A leftover JSON temporary file is not a validated replacement for
the destination. Atomic replacement alone is not a power-loss durability or
concurrent-writer guarantee. Stop other writers before inspecting or retrying.

## Citation updates do not reach the pages

`resolve-dois` and `format-citations` change the selected citation store, not
existing registries. Run `build-registry --doi-cache PATH` with that store, then
`render-group`. An unresolved DOI is not necessarily a transport failure: the
offline inference rule covers only recognised JHEP patterns, and ambiguous
INSPIRE results remain unresolved. Manual entries are protected even with
`--refresh-existing`.

If a citation command reports that `--doi-cache` is required, choose a writable
store outside the installation and pass its path explicitly. To retain bundled
entries, [copy the dictionary first](citations.md#choose-a-store). Use the same
path with build commands. A missing path starts empty; it does not inherit the
bundled citations. Keep user updates outside installed shared data, which may
be read-only or replaced during an upgrade.

## Missing records or inactive page controls

| Symptom | Check and remedy |
| --- | --- |
| A publication is missing | Reset browser filters, then inspect `view-report.json`. Check the publication policy, lifecycle and explicit relationships; ongoing membership is a separate decision. |
| No publications after editing a policy | An explicitly empty policy selects none. A missing group table instead warns and uses the internal identifier fallback. |
| Only three of four synthetic notes appear | The fourth is superseded and initially hidden. Enable the superseded status filter. |
| A filter reappears after reload | Filters and sorting persist in the URL. Use the page's Reset control. |
| Records are readable but controls do nothing | Load the [browser assets](rendering.md#enable-browser-assets), with common files first. Check browser network errors and asset paths relative to the site's docs directory. |
| Navigation works at `/` but breaks under a repository path | Test through the preview server at the configured subpath. The documentation preview uses `/glance-analysis-lister/`; see the [site guide](site.md). |
| Editing a generated page has no lasting effect | Edit the original Markdown or synthetic fixture. The documentation helper regenerates `site-src/` and `site/`; restart after renderer-code changes. |

Selection and derivation details are explained in the
[diagnostic report guide](diagnostics.md). For integration changes, the
[browser checks](development.md#browser-and-site-checks) exercise asset loading,
instant navigation and URL persistence with synthetic records.
