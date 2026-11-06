# Development and validation

[Documentation index](README.md)

## Set up and run checks

Use Python 3.13, matching CI. From the repository root, create and activate
`.venv` as shown in the [quick start](../README.md#install-and-try-without-credentials),
then install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

This installs the package in editable mode. Reinstall after changing dependencies
or package metadata. Run the offline checks and build:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
git diff --check
python -m build
```

`python -m build` creates a source distribution and builds the wheel from it.
CI installs that wheel in a clean environment and runs
`scripts/check_distribution.py` to verify the CLI, synthetic rendering, packaged
assets, dictionaries, policies and licences.

## Choose regression coverage

The [field walkthrough](contributing-field.md) follows a synthetic trigger from
API input to stored data, prepared search metadata and a rendered analysis card.
Use it to locate the right layer and select tests for a contribution.

View tests cover preparation, ongoing pages, papers, notes, shared controls,
publication policies and output generation. Use the shared synthetic fixtures
in `tests/view_fixtures.py`; construct new records independently of private data.
For a manual example, follow the [quick start](../README.md#install-and-try-without-credentials).

`tests/test_retained_field_contract.py` checks source-field access during
preparation and rendering. A lookup outside `registry/fields.py` fails with its
resource and nested path, even when the fixture lacks that field. Tests cover
populated and sparse records. Add cases for new conditional behaviour; output
comparisons also verify that trimming fields preserves rendering and search data.

## Compatibility checks

Use this map when changing a [supported interface](compatibility.md). Keep the
existing expectations unless the change explicitly follows the versioning and
migration policy. A new fixture supplements a frozen fixture; it does not replace
one.

| Surface | Main regression coverage |
| --- | --- |
| CLI options, defaults and streams | `tests/test_workflow_cli.py`, `tests/test_console.py`, `tests/test_doi_resolution.py`; installed CLI checks in `scripts/check_distribution.py`. |
| Curated v2 and reader | `tests/test_registry_contract.py`, `tests/test_curated_reader.py`, frozen `tests/fixtures/curated/` inputs and retained-field checks. |
| Publication configuration | `tests/test_publication_curation.py`, `tests/test_view_contracts.py`: defaults, validation, OR selection, missing versus empty policies. |
| Python preparation | `tests/test_view_contracts.py`, `tests/test_view_preparation.py`: typed results, metadata, explicit relationships and preparation without I/O or renderers. |
| Generated names and record fragments | `tests/test_generated_contract.py`: names and literal IDs survive title, public-label and ordering changes. |
| Filter URLs and site integration | `tests/browser/check_zensical.py`: literal saved URLs as well as links produced by current controls; `check_demo.py` runs these on both demo sites. Standalone browser checks also cover history, keyboard operation and no-JavaScript output. |
| Report summary and diagnostics | `tests/test_generated_contract.py`, `tests/test_view_diagnostics.py`: versioned summary types and counts, plus diagnostic severity and inclusion behaviour. |
| Bundled data and reproducibility | Citation/registry tests and `tests/test_render_reproducibility.py`: explicit store selection, manual entries, fingerprints, stable output and unchanged-file handling. |

These checks establish a maintained baseline. They do not prove compatibility
with an arbitrary historical package or consuming theme. The
[release procedure](releases.md) requires evaluation of the actual candidate and
supported upgrade paths.

## Browser and site checks

Install Chrome, a compatible ChromeDriver and the site-test requirements:

```bash
python -m pip install -r tests/browser/requirements.txt
```

These requirements reuse the Zensical pin in `requirements-docs.txt`.
`CHROME_BINARY` can select the Chrome executable; supply the driver explicitly:

```bash
python tests/browser/check_ongoing.py --driver /path/to/chromedriver
python tests/browser/check_papers.py --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource confnotes --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource pubnotes --driver /path/to/chromedriver
python tests/browser/check_zensical.py --driver /path/to/chromedriver
python tests/browser/check_demo.py --driver /path/to/chromedriver
```

CI checks Chrome/ChromeDriver compatibility and sandboxed startup before running
these checks. The Zensical test builds strictly, serves on loopback and checks
instant navigation, repeat visits, search/filter URLs, ongoing sort persistence,
reset, expansion and stylesheets. It covers the built-in theme, not consumer theme
overrides. Tests remove their temporary sites, HTML, screenshots and driver logs.

The demo check follows the documented generation commands, starts the standalone
preview, exercises the empty-policy tutorial and restores the original output.
It also builds the documentation and checks all four embedded demo pages under
the repository subpath. Both sites reuse the instant-navigation and filter checks.

The offline, browser and documentation CI jobs must pass before the release job
creates a draft release from a tag. The documentation job also supplies an
[HTML artifact for review](site.md#inspect-a-ci-build). All test data is invented;
these checks do not establish live CERN authentication. To preview the
documentation itself, use the [local site guide](site.md).

For version changes, artifact checks and the tag workflow, follow
[release qualification](releases.md). The [compatibility guide](compatibility.md)
defines the current interface boundaries; the [upgrade guide](upgrading.md)
describes how consumers can evaluate a candidate using saved data.
