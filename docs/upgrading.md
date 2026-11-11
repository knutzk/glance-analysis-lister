# Upgrading and compatibility

Test the candidate package alongside the working version, using saved data and
a separate output directory. Keep the old environment and site until you have
checked the candidate. Keep custom policies and citation stores outside the Python
environment so reinstalling the package cannot replace your edits.

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

## What can change

Pin a package version or commit for a repeatable workflow. The current 0.x policy
preserves documented commands, Python calls, configuration, generated names and
URL meanings in patch releases. Bug fixes and bundled citation/policy updates
can still change the resulting pages. Breaking interface changes require a minor
release and migration instructions; a deprecation period is preferred but not
guaranteed before v1.0. This is not a retrospective guarantee for every old release.

| Use | Boundary to rely on |
| --- | --- |
| Shell automation | Documented CLI options and exit status. Results use stdout, diagnostics stderr; log wording and ordering are not a data protocol. |
| Saved registries and reports | The current [file-format rules](file-reference.md). Package and JSON versions are independent; a package minor release does not waive the stored-format rules. |
| Python integration | Only the imports and result attributes in the [Python guide](python-access.md). |
| Website integration | Generated filenames, assets and emitted record/filter URLs. HTML layout, CSS classes and JavaScript internals are not extension APIs. |
| Publication policies | Documented TOML fields and defaults, including the difference between missing and empty policies. Bundled contents may change. |

Citation and identifier updates affect newly built registries; policy changes
affect prepared views. Compare results with the same saved source data and keep
the provenance. A copied URL retains its meaning, but the available records can
change. The consuming website owns path prefixes and redirects.

For v1.0 onward, the planned policy preserves supported interfaces across a major
series: patches fix bugs; minor releases may add compatible features. Deprecations
provide a replacement and migration guidance and remain supported for that major
series; removal or incompatible reinterpretation requires a new major release.
CLI/configuration warnings would remain visible with `--quiet`, and Python would
use caller-located `DeprecationWarning`. No interface is currently deprecated
under that policy. Urgent exceptions must explicitly state impact and recovery;
they cannot silently redefine a stored field within its schema version.

## Release history

- [v0.2.0](https://github.com/knutzk/glance-analysis-lister/blob/main/.github/release-notes/v0.2.0.txt)
- [v0.1.0](https://github.com/knutzk/glance-analysis-lister/blob/main/.github/release-notes/v0.1.0.txt)
