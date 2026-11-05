# Compatibility and versioning

[Documentation index](README.md)

The package is in the 0.x series. The documentation identifies the interfaces
intended for consumers; it does not promise that every 0.x upgrade is compatible.
Pin an exact version or commit, review the matching release notes and follow the
[upgrade procedure](upgrading.md) before replacing a working installation.

## Interface boundaries

| Interface | Current scope | Upgrade considerations |
| --- | --- | --- |
| CLI | The eight commands, `--version` and options in the [reference](cli-reference.md). | Results go to stdout and diagnostics to stderr. Use exit status to detect failure; human-readable summaries, log wording and ordering are not a machine-readable protocol. |
| Curated registry | The [v2 contract](curated-format.md), including optional additions, independent identities and missing/null/empty distinctions. | Existing v2 fixtures remain readable. A breaking stored-format change requires a new schema version and explicit migration support. |
| Publication policies | The TOML fields and defaults in [rendering and policies](rendering.md#publication-policies). | Missing and explicitly empty policies have different meanings. Bundled policy contents can change between releases. |
| Python | Only the imports and result attributes in [Python access](python-access.md). | Reader methods return copies; prepared objects are consumed as read-only values. Other helpers and nested rule evidence are internal. |
| Generated pages | Four Markdown filenames, generated browser assets and the integration described in [rendering](rendering.md). | Deploy pages and assets from the same generation. HTML structure, CSS classes and internal JavaScript functions are not a supported extension API. |
| Record/filter URLs | The current controls and links described in [ongoing analyses](ongoing.md) and [publication tables](publications.md). | Browser tests cover current URL persistence; compatibility with all URLs from earlier releases is not yet promised. |
| Diagnostic reports | Current `view-report.json`, labelled schema version 2 and explained in [diagnostics](diagnostics.md). | Useful for inspection, but not yet a stable external JSON API. Rule identifiers, evidence dictionaries and reason strings may change; do not infer stability from the version number alone. |
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
| Diagnostic schema version | Report `schema_version` | The current report layout, without a complete compatibility promise. |
| Generator revision and hashes | Generated provenance headers and report | The implementation and inputs used to create particular output. |

To identify the installed package:

```bash
analysis-lister --version
```

A future package v1.0 can still use curated schema v2. Changing a JSON version
number by hand is not a migration. See [curated compatibility](curated-format.md#compatibility-policy)
for the rules governing format changes.

## What remains to settle before v1.0

The support scope above is the starting point for a stable release. Before v1.0,
the project still needs an explicit deprecation policy, compatibility checks
across supported package versions, and decisions on long-lived generated URLs
and diagnostic-report consumers. Citation updates require an explicit writable
store; builds read bundled data by default. See [citation maintenance](citations.md)
for persistence and upgrade behaviour.

Current tests establish offline and browser behaviour for their tested
environments; they do not establish live CERN login or support on every platform
allowed by package metadata. See [development and validation](development.md)
for the checks and [release qualification](releases.md) for the evidence required
before publishing a candidate.
