# Upgrading an installation

[Documentation index](README.md)

Test the candidate package alongside the working version, using saved data and
a separate output directory. Keep the old environment and site until you have
checked the candidate. The [compatibility guide](compatibility.md) distinguishes
the Python API, CLI and stored-data contracts.

## Preserve the inputs

Record the installed package version and resolved dependencies:

```bash
analysis-lister --version
python -m pip freeze > previous-environment.txt
```

For an older installation without `--version`, use
`python -c 'from importlib.metadata import version; print(version("glance-analysis-lister"))'`.

Review that environment file before sharing it: direct dependency URLs can
contain private locations. Keep copies of the API and curated snapshots,
publication policy, custom citation store, consuming-site configuration and
working generated output. Store real data privately.

If an older workflow changed the shared citation store, or you edited the
installed publication policy, copy those files outside the environment before
upgrading. Package data can be replaced during installation. Pass explicit
`--doi-cache` and `--curation-config` paths consistently when comparing versions.
Citation update commands now require an explicit `--doi-cache` path; registry
builds still read bundled citations when no override is supplied. There is no
automatic migration of previous edits or merge into a new store.
Do not carry cookie files into a public reproduction or documentation build.

## Install and compare separately

Create a Python 3.13 environment for the candidate and install the wheel you
intend to evaluate. Replace the wheel path with your actual artifact:

```bash
python3.13 -m venv .venv-candidate
.venv-candidate/bin/python -m pip install /path/to/glance_analysis_lister-VERSION-py3-none-any.whl
.venv-candidate/bin/python -m pip check
```

From the matching source checkout or source archive, first run the
[synthetic demo](../examples/README.md) using that environment. Examples and
documentation are in the source archive, not the wheel. Then render your saved
curated registry to a separate destination:

```bash
.venv-candidate/bin/analysis-lister render-group --group TOPQ \
  --snapshot data/previous-curated.json \
  --curation-config data/publication-curation.toml \
  --output-dir pages/candidate
```

Substitute your group, inputs and destinations. This isolates changes in view
preparation and rendering without downloading data or rebuilding the registry.
Review selected counts and diagnostics, then check the pages with the candidate's
assets in your site's theme. Exercise existing record links, filter URLs, keyboard
operation and any custom styling; generated HTML internals are not a stable API.

To assess curation or bundled-data changes as well, rebuild from the same saved
API snapshot and compare with the previous curated file:

```bash
.venv-candidate/bin/analysis-lister build-registry \
  --api-snapshot data/previous-api.json \
  --doi-cache data/doi-metadata.json --output data/candidate-curated.json
.venv-candidate/bin/analysis-lister compare-snapshots \
  data/previous-curated.json data/candidate-curated.json --details \
  --output data/upgrade-comparison.json
```

Both compared registries must be supported by the candidate and from the same
endpoint. A new output path has no previous count-drop baseline: examine the
comparison explicitly. Dictionary and curation changes can explain differences
even when the API bytes are identical. Rerender with the candidate registry after
reviewing them. [Provenance](data.md#trace-your-output) identifies the inputs and code used.

If the candidate fails, keep using the previous environment and generated site.
Do not overwrite the old snapshot or attempt an undocumented reverse migration.
Once the candidate is accepted, switch the consuming workflow to it and publish
the matching pages and assets through your normal review process.

## Migrate from the v0.1 workflow

The 0.2 workflow replaces CSV-derived registries and legacy Python models with
API snapshots, curated v2 data and prepared views. There is no converter for the
old registry format. Obtain a supported API snapshot through an authorised
download, or use an existing saved API snapshot, then build the registry offline.
HTML CSV exports remain independent and cannot feed `build-registry`.

| Previous integration | Current replacement |
| --- | --- |
| CSV-derived registry and legacy model imports | `build-registry` from API JSON; the documented [reader and prepared-view API](python-access.md). |
| Lookup dictionaries and group-specific download settings | Retrieve accessible records once; apply group membership and explicit TOML publication policies during preparation. |
| Fixed or combined publication views | Separate `ongoing.md`, `papers.md`, `confnotes.md` and `pubnotes.md`; update site navigation and [enable assets](website.md#enable-browser-assets). |
| Optional download dependencies | The `html` extra for HTML/CSV export; API retrieval is included in normal installation. |
| Citation `locked` flag | Protect manual entries with `source = "manual"`; remove the obsolete flag and preserve citation provenance. |
| Obsidian export | Removed; there is no replacement command. |

Rewrite command invocations against the [current CLI reference](cli-reference.md);
compatibility aliases for retired commands and options are not provided. The
[release notes](releases.md#release-notes) give the detailed change history.
