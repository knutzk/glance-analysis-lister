# Releases and qualification

This guide describes how to prepare and check a release. A passing development
test run is evidence for a candidate, not permission to tag, push or publish it.
Consumers should follow [upgrading](upgrading.md); contributors should start with
[development and validation](development.md).

## Prepare an exact candidate

Choose the commit and version together. Review the public interfaces and bundled
data changes, update `pyproject.toml` and version-specific README wording, and
maintain `.github/release-notes/vVERSION.txt`. The tag must be `vVERSION`; CI checks
that it matches package metadata and that the notes exist and are nonempty.

Release notes should explain user-visible changes, affected interfaces, migration
steps, bundled policy/citation changes and known limitations. Record validation
with the candidate revision and environment. Keep historical notes as a record
of their release rather than updating their old test counts to today's totals.

Use a clean checkout containing only the intended public files. Ignoring a file
in Git does not itself exclude it from a distribution: package discovery and
source-manifest rules also apply. Inspect source and wheel contents, especially
when local experimental modules or private inputs exist in a working checkout.

## Build and validate

Run the [offline and browser checks](development.md), including the complete
synthetic demo. Build the strict documentation site with
`python scripts/docs.py build`. Test the candidate in the consuming site, where
theme overrides and navigation may differ from the test site.

From the clean candidate checkout, build the source archive and its wheel:

```bash
python -m build
```

Without `--wheel` or `--sdist`, this builds the wheel from the source archive.
Use a fresh output directory so `dist/` contains exactly one candidate source
archive and wheel. In a clean environment, install the actual wheel and run the
distribution check from the candidate checkout:

```bash
python3.13 -m venv /tmp/glance-release-check
/tmp/glance-release-check/bin/python -m pip install dist/glance_analysis_lister-VERSION-py3-none-any.whl
/tmp/glance-release-check/bin/python -m pip check
/tmp/glance-release-check/bin/python -I scripts/check_distribution.py
```

Replace `VERSION` with the candidate version and use a new environment path if
that directory already exists. The check exercises installed CLI workflows and
synthetic rendering, and verifies packaged resources, source revision and
licences. Documentation, examples and screenshots belong in the source archive;
runtime schemas, browser assets, dictionaries, policies and certificates belong
in the wheel. Private data and local guidance belong in neither.

Also unpack the source archive into a separate directory, install its
`requirements-docs.txt` in a documentation environment and build the site there.
This catches missing documentation inputs that a build from the checkout can
hide. For cross-version qualification, apply the [upgrade procedure](upgrading.md)
and keep the frozen curated fixtures unchanged.

Record what was actually tested. CI uses Python 3.13 on Ubuntu and runner Chrome;
package metadata allowing newer Python versions does not mean they were tested.
Live CERN login, credential reuse and downloads require a separately authorised
acceptance run. Synthetic checks cannot establish those outcomes.

## What CI does

Pushes and pull requests run offline/package checks, browser tests and a strict
documentation build. The documentation job uploads a review artifact for
14 days; see [how to inspect it](site.md#inspect-a-ci-build).

For a pushed `v*` tag, all three jobs must succeed before the release job creates
a **draft GitHub release** with the verified wheel, source archive and matching
notes. The distribution artifact used between jobs is retained for 7 days.
Tag checks reject mismatched versions or missing notes. The draft still requires
review before publication. The workflow does not publish to a package index or
deploy documentation to GitHub Pages.

## Documentation versions

The current site is labelled **development** and reflects the checkout used to
build it. There is no hosted stable-version selector or retention promise yet.
For a release, use the source archive or exact tag to build matching documentation
and the synthetic demo. Do not use today's development docs as the reference for
an older installed package.

A release review should retain the exact source revision, resolved dependency
versions and build results alongside its artifacts. The Zensical dependency is
pinned, but the full dependency graph is not locked; rebuilding at a later date
is not a promise of byte-identical HTML. A short-lived CI artifact is not a
permanent documentation archive. Hosted stable/development URLs and retention
of old documentation must be decided before documentation publication begins.

## Release notes

Maintained notes live in `.github/release-notes/`: `v0.2.0.txt` covers the API
workflow, curated v2 and group views; `v0.1.0.txt` describes the historical
CSV-based workflow.

These files describe their versions; their presence does not establish that a
release has been published or that its validation covers the current checkout.
