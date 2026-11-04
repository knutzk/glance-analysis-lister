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

View tests cover preparation, ongoing pages, papers, notes, shared controls,
publication policies and output generation. Use the shared synthetic fixtures
in `tests/view_fixtures.py`; construct new records independently of private data.
For a manual example, follow the [quick start](../README.md#install-and-try-without-credentials).

`tests/test_retained_field_contract.py` checks source-field access during
preparation and rendering. A lookup outside `registry/fields.py` fails with its
resource and nested path, even when the fixture lacks that field. Tests cover
populated and sparse records. Add cases for new conditional behaviour; output
comparisons also verify that trimming fields preserves rendering and search data.

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
```

CI checks Chrome/ChromeDriver compatibility and sandboxed startup before running
these checks. The Zensical test builds strictly, serves on loopback and checks
instant navigation, repeat visits, search/filter URLs, ongoing sort persistence,
reset, expansion and stylesheets. It covers the built-in theme, not consumer theme
overrides. Tests remove their temporary sites, HTML, screenshots and driver logs.

Both offline and browser CI jobs must pass before the release job creates a draft
release from a tag. All test data is invented; these checks do not establish live
CERN authentication. To preview the documentation itself, use the
[local site guide](site.md).
