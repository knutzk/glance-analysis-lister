# Development and validation

[Documentation index](README.md)

## Supported validation scope

The current maintenance target is Python 3.13 on Ubuntu and macOS, with Chrome
and the pinned Zensical default theme for interactive pages. Coverage differs
by environment:

| Surface | Automated acceptance | Manual acceptance and limits |
| --- | --- | --- |
| Python and CLI | Python 3.13 on GitHub's `ubuntu-latest` runner: offline regressions, dependency checks, source build and clean installed wheel. | Repeat these checks on macOS for a release candidate. Development runs have passed on macOS 26 arm64 with Python 3.13.12; that does not qualify every macOS version or Intel hardware. |
| Browser controls | Runner-installed Chrome and matching ChromeDriver, headless, on Ubuntu. Standalone views and both demo sites are checked. | For a candidate, repeat on macOS Chrome and inspect keyboard focus and narrow-screen behaviour. Firefox, Safari, Edge and mobile browsers are not yet qualified. |
| Site integration | The version pinned in `requirements-docs.txt` (currently Zensical 0.0.58), default theme, instant navigation, repository subpath and strict links. | Check the actual consuming site's theme, assets and URL prefix. Other generators and theme overrides are not covered by the default-theme tests. |
| Storage and recovery | Synthetic exceptions and interrupts on local filesystems, followed by real retry/offline recovery commands. | Concurrent writers, network filesystems and power-loss durability are outside the tested guarantees. |
| CERN authentication and live retrieval | Synthetic clients and saved HTML only. | Fresh login, credential reuse and live downloads need a separately authorised acceptance run. They are not qualified by offline CI. |

Package metadata permits Python >=3.13; newer interpreters are not yet part of
the tested support scope. Windows is also unqualified. A successful install on
an untested environment does not establish workflow support there. When adding
a supported environment, add repeatable checks or an explicit manual acceptance
record before expanding these claims.

CI records the resolved Python, operating system, architecture and dependencies;
the browser job also records Chrome and ChromeDriver versions. Runner images and
unlocked dependencies change, so use the logs from the exact candidate rather
than treating `ubuntu-latest` or "Chrome" as a fixed version. For a manual run,
record the revision, environment, commands, results and any skipped checks using
the [release acceptance record](releases.md#record-operational-acceptance).

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

## Recovery checks

`tests/test_download_errors.py` injects authentication, HTTP-status, network,
response-validation and pagination failures through the CLI. It checks distinct
remedies, exit status 1, preserved output bytes and absence of synthetic secrets
in normal, quiet and verbose output, including nested exception chains. A curated
schema failure retains its field path without exposing the invalid value.
The HTML transport checks also verify certificate verification, bounded timeouts
and absence of automatic retries.

`tests/test_refresh_recovery.py` runs the real download publication, registry
builder and renderer against a synthetic API client. It interrupts pagination
and registry replacement, rejects count drops independently at download and
build time, and fails a file replacement in the second of three groups. Tests
check saved bytes and stage diagnostics, then execute the documented retry or
offline recovery commands. Recovered pages match a fresh render; completed groups
keep their bytes, timestamps and inodes. Network connections are forbidden, and
offline recovery also forbids construction of the authentication/client objects.

`tests/test_html_storage.py` covers batch rollback and failed rollback. A complete
offline HTML replay repairs the destination and clears its interruption marker
while leaving earlier recovery files available. `tests/test_storage.py` covers
failed flushes and atomic replacements. Run these focused checks with:

```bash
python -m unittest discover -s tests -p 'test_refresh*.py' -v
python -m unittest discover -s tests -p 'test_*storage.py' -v
```

See the [recovery table](troubleshooting.md#resume-an-interrupted-workflow) for
operator actions. These tests do not simulate machine power loss, filesystem
corruption or simultaneous writers, and do not establish live login or network
reliability.

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
