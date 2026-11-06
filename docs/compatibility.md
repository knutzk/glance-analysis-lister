# Compatibility and versioning

[Documentation index](README.md)

The package is in the 0.x series. This page defines the supported interface scope
and the change policy below; it does not retroactively guarantee compatibility
with every earlier 0.x release. Pin an exact version or commit, review the
matching release notes and follow the
[upgrade procedure](upgrading.md) before replacing a working installation.

## Interface boundaries

| Interface | Current scope | Upgrade considerations |
| --- | --- | --- |
| CLI | The eight commands, `--version` and options in the [reference](cli-reference.md). | Results go to stdout and diagnostics to stderr. Use exit status to detect failure; human-readable summaries, log wording and ordering are not a machine-readable protocol. |
| Curated registry | The [v2 contract](curated-format.md), including optional additions, independent identities and missing/null/empty distinctions. | Existing v2 fixtures remain readable. A breaking stored-format change requires a new schema version and explicit migration support. |
| Publication policies | The TOML fields and defaults in [rendering and policies](rendering.md#publication-policies). | Missing and explicitly empty policies have different meanings. Bundled policy contents can change between releases. |
| Python | Only the imports and result attributes in [Python access](python-access.md). | Reader methods return copies; prepared objects are consumed as read-only values. Other helpers and nested rule evidence are internal. |
| Generated pages | Four Markdown filenames, generated browser assets and the integration described in [rendering](rendering.md). | Deploy pages and assets from the same generation. HTML structure, CSS classes and internal JavaScript functions are not a supported extension API. |
| Record/filter URLs | The emitted record fragments and parameters in the [generated URL contract](rendering.md#generated-file-and-url-contract). | Preserve the group and native identity for stable fragments. The consuming site owns URL prefixes and redirects; data and policy changes can change which records a link shows. |
| Diagnostic reports | The [supported v2 summary](diagnostics.md#supported-report-summary): identity, input/generator fingerprints and counts. | Summary fields retain names, types and meanings within v2; additions are allowed. Detailed evidence, issue codes and reason strings remain internal. |
| Bundled metadata | Citation dictionary, public-note identifiers and publication policies. | Content changes can alter new registries or views without changing the stored schema. Preserve overrides and compare results. |

The command-line and curated-data interfaces serve different purposes. A CLI
formatting change need not affect saved data, and a curated schema addition need
not require a new command. The Python scope does not turn the entire package's
module layout into a public API.

## Package and data versions

These version numbers are independent:

| Version | Where to find it | What it identifies |
| --- | --- | --- |
| Package version | Installed distribution metadata; `pyproject.toml` in a checkout | The code and bundled data release. |
| Curated schema version | Registry `schema_version` | The stored data contract; currently `2`. |
| Diagnostic schema version | Report `schema_version` | The supported report-summary contract; detailed traces are not versioned external APIs. |
| Generator revision and hashes | Generated provenance headers and report | The implementation and inputs used to create particular output. |

To identify the installed package:

```bash
analysis-lister --version
```

A future package v1.0 can still use curated schema v2. Changing a JSON version
number by hand is not a migration. See [curated compatibility](curated-format.md#compatibility-policy)
for the rules governing format changes.

## Change and deprecation policy

This policy applies to the documented interfaces above. It does not freeze every
internal import, generated HTML element, diagnostic explanation or bundled data
value. Adding a citation, changing a publication policy, or correcting selection
to match documented rules can change output without changing an interface.
Describe user-visible changes in release notes and retain their provenance.

### During the 0.x series

- Patch releases preserve the documented commands, supported Python calls and
  result attributes, configuration inputs, generated names and URL semantics.
  They may fix implementation bugs and update bundled data.
- A breaking interface change requires a new minor version, release notes that
  identify affected consumers, and upgrade instructions. A deprecation period is
  preferred but is not guaranteed before v1.0.
- The curated v2 and report-summary v2 rules apply independently: a breaking
  change to either stored contract still requires its own schema-version change.
  A package minor version does not waive that requirement.

The unreleased CLI changes documented in [releases](releases.md#unreleased-cli-changes)
therefore require a minor release after v0.2.0, not a v0.2 patch. The version in
the working checkout is updated when selecting that candidate.

### From v1.0 onward

This is the policy planned for v1.0 and later. The current 0.x series follows
the rules above:

- Patch releases fix bugs while preserving supported interfaces. Minor releases
  may add commands, optional arguments and fields while accepting existing
  supported inputs and preserving their documented meanings.
- Deprecate a supported interface in a minor release, provide a replacement and
  migration instructions, and keep the old interface working for the rest of
  that major series. Removal or incompatible reinterpretation requires the next
  major release. Record the deprecation and earliest removal version in release
  notes; do not silently turn an old option into a different operation.
- CLI/configuration deprecations use stderr warnings that remain visible with
  `--quiet`. Python deprecations use `DeprecationWarning` with the caller as the
  warning location. No supported interface is currently marked deprecated under
  this policy, so no warning mechanism is added merely for future use.
- A format change needs explicit migration guidance and supported-input tests;
  readers must not guess a version or invent missing history. Moving hosted page
  paths remains the consuming site's responsibility. Preserve emitted record
  fragments and filter meanings within a supported major series.

If an urgent correctness or security fix cannot preserve an interface, record
the exception, affected versions, impact and recovery steps explicitly. It is
not permission to silently change a stored field's meaning within its schema
version.

## Review a compatibility change

Identify the affected interface and whether the change is additive, a correction
to documented behaviour, a deprecation, or a break. Add a focused regression
using independently invented inputs, retain existing compatibility fixtures,
and update the reference and migration guidance in the same change. Do not
rewrite a saved-link baseline simply to make an incompatible change pass.

Current [contract checks](development.md#compatibility-checks) cover the declared
scope. Qualifying a stable release still requires checks against the selected
candidate and supported prior versions; passing today's tests is not that
qualification. Citation updates require an explicit writable store, while
builds read bundled data by default; see [citation maintenance](citations.md)
for persistence and upgrade behaviour.

Current tests establish offline and browser behaviour for their tested
environments; they do not establish live CERN login or support on every platform
allowed by package metadata. See [development and validation](development.md)
for the checks and [release qualification](releases.md) for the evidence required
before publishing a candidate.
