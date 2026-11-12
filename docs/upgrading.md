# Upgrading and compatibility

Test the candidate package alongside the working version, using saved data and
a separate output directory. Keep the old environment and site until you have
checked the candidate. Keep custom policies and citation stores outside the Python
environment so reinstalling the package cannot replace your edits.

## Upgrading to v0.4.0: GROVE

Version 0.4.0 is the first release of **GROVE** (GLANCE Records Organised for
Viewing and Exploration). It replaces the installation, command and import names:

| Interface | Previous name | New name |
| --- | --- | --- |
| Python distribution | `glance-analysis-lister` | `glance-grove` |
| Shell command | `analysis-lister` | `grove` |
| Python imports and module invocation | `analysis_lister` | `grove` |
| GitHub repository | `knutzk/glance-analysis-lister` | `knutzk/glance-grove` |

There are no aliases or import shims for the old names. Update scripts, scheduled
commands, Python imports and dependency declarations. Install the candidate into
a fresh virtual environment: pip treats the two distribution names as separate
projects, so installing `glance-grove` does not remove the old installation.
Use `grove --version` or `python -m grove --version` to check the candidate.
For a source checkout, update the Git remote to
`https://github.com/knutzk/glance-grove.git` after the repository rename.

Saved snapshot filenames and the curated data schema have not changed. Valid
saved snapshots still load; their old generator identity may produce a warning.
Rebuild from a saved API snapshot and render into a separate directory to record
the new generator identity. This needs no fresh CERN download. Preserve custom
stores and policies and pass their paths explicitly as before. Bundled data in
an installed wheel now lives under `share/glance-grove/`.

Historical v0.1.0–v0.3.0 tags, release notes and artifacts describe the old package.
They are not GROVE distributions and must not be renamed or uploaded to the
`glance-grove` PyPI project. The examples below describe the candidate interface.

## Restoring full paper citations

Paper details again include a **Cite as** block. To recover final TeX and full
titles omitted by earlier curated snapshots, rebuild the registry from your
saved API snapshot with `build-registry`, then rerun `render-group`. Keep the
same explicit `--doi-cache` when using a custom citation store. No download is
needed. Older curated snapshots remain readable and use the short title (or
native identifier) when the fuller titles are unavailable.

## Preserve the inputs

Record the installed package version and resolved dependencies:

```bash
grove --version
python -m pip freeze > previous-environment.txt
```

For the previous package, use `analysis-lister --version`, or
`python -c 'from importlib.metadata import version; print(version("glance-analysis-lister"))'`
if that installation predates `--version`.

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
automatic migration of previous edits or merge into a new store. Custom citation
stores contain user-maintained work, including protected manual entries; they
cannot simply be regenerated from GLANCE. Keep the original store and provenance,
and check that your entries survive any documented conversion before switching
to a new copy. If a future package cannot read it and provides no conversion,
keep using the earlier environment until those edits can be preserved.
Do not carry cookie files into a public reproduction or documentation build.

## Install and compare separately

Create a Python 3.13 environment for the candidate and install the wheel you
intend to evaluate. Replace the wheel path with your actual artifact:

```bash
python3.13 -m venv .venv-candidate
.venv-candidate/bin/python -m pip install /path/to/glance_grove-VERSION-py3-none-any.whl
.venv-candidate/bin/python -m pip check
```

From the matching source checkout or source archive, first run the
[synthetic demo](../examples/README.md) using that environment. Examples and
documentation are in the source archive, not the wheel. Then render your saved
curated registry to a separate destination:

```bash
.venv-candidate/bin/grove render-group --group TOPQ \
  --snapshot data/previous-curated.json \
  --curation-config data/publication-curation.toml \
  --output-dir pages/candidate
```

Substitute your group, inputs and destinations. This isolates changes in view
preparation and rendering without downloading data or rebuilding the registry.
Review selected counts and diagnostics, then check the pages with the candidate's
assets in your site's theme. Exercise existing record links, filter URLs, keyboard
operation and any custom styling; generated HTML internals are not a stable API.

To assess curation or bundled-data changes, rebuild from the same saved API
snapshot. If the candidate can also read the previous curated file, compare them:

```bash
.venv-candidate/bin/grove build-registry \
  --api-snapshot data/previous-api.json \
  --doi-cache data/doi-metadata.json --output data/candidate-curated.json
.venv-candidate/bin/grove compare-snapshots \
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

## If a saved file is no longer supported

A different generator fingerprint, or missing metadata, produces an advisory
warning. Valid data can still be read and rendered. The fingerprint compares code
contents, so an identical package in another worktree or a documentation-only
commit does not require regeneration. If problems occur, regenerate the affected
files with the current package rather than editing their metadata.

A curated registry is a generated intermediate file. If it fails structural
validation with the candidate, use `build-registry` with your saved API snapshot
and a new output path, as above. Then render from that new registry to regenerate the pages and
report. Existing files should remain untouched until you accept the result.

If the candidate cannot read the API snapshot either, retain the earlier package
for those files or obtain a fresh snapshot through an authorised CERN download.
There is no general migration tool or promise that future packages will read
every older snapshot. Invalid data still fails even though generator mismatches
only warn. Legacy schema-version numbers are ignored.

Snapshot comparison requires both inputs to be supported. If the old registry is
unreadable, compare the old and new generated pages and reported counts instead.
This does not provide the field-level comparison available for compatible inputs.
Apply the separate preservation steps above to custom citation stores and policies.

## What can change

Pin a package version or commit for a repeatable workflow. The current 0.x policy
preserves documented commands, Python calls, configuration, generated names and
URL meanings in patch releases. Bug fixes and bundled citation/policy updates
can still change the resulting pages. Breaking interface changes require a minor
release and upgrade instructions; a deprecation period is preferred but not
guaranteed before v1.0. This is not a retrospective guarantee for every old release.

| Use | Boundary to rely on |
| --- | --- |
| Shell automation | Documented CLI options and exit status. Results use stdout, diagnostics stderr; log wording and ordering are not a data protocol. |
| Generated JSON | Internal workflow files; structure is validated and generator mismatches only warn. Retained fields and report structures can change; upgrades may require rebuilding. See [saved-file handling](#if-a-saved-file-is-no-longer-supported). |
| Python integration | Only the imports and result attributes in the [Python guide](python-access.md). |
| Website integration | Generated filenames, assets and emitted record/filter URLs. HTML layout, CSS classes and JavaScript internals are not extension APIs. |
| Publication policies | Documented TOML fields and defaults, including the difference between missing and empty policies. Bundled contents may change. |
| Custom citation stores | User-maintained entries and provenance must be preserved. Any required format conversion needs instructions that retain those edits. |

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
recovery guidance must distinguish regenerable output from user-maintained data.
These public-interface policies do not make generated JSON a stable API. Internal
format changes need validation and a clear rebuild or recovery path, rather than
indefinite support for every previous file shape.

## Release history

- [v0.4.0](https://github.com/knutzk/glance-grove/blob/main/.github/release-notes/v0.4.0.txt)
- [v0.3.0](https://github.com/knutzk/glance-grove/blob/main/.github/release-notes/v0.3.0.txt)
- [v0.2.0](https://github.com/knutzk/glance-grove/blob/main/.github/release-notes/v0.2.0.txt)
- [v0.1.0](https://github.com/knutzk/glance-grove/blob/main/.github/release-notes/v0.1.0.txt)
