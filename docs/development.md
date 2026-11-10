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

The ongoing check also verifies that filtering preserves card order, focus and
expansion without moving unchanged cards. A 1,000-analysis synthetic collection
exercises distant permalinks and keyboard expansion at desktop and narrow widths;
print media must render card content without deferring offscreen layout.

The shared `tests/browser/accessibility.py` checks use real Tab/Shift+Tab and
Enter/Space navigation for search, filters, sorting and disclosures, including
focus returning to the heading after Collapse. They verify accessible control
names, pressed/expanded state, live result counts and visible focus outlines.
At 390- and 320-pixel CSS viewports, light/dark layouts keep the page within the
viewport while archive tables scroll with arrow keys. With JavaScript disabled,
all four records and their details remain readable, including superseded notes;
inactive filters stay hidden. Both demo sites run these checks through
`check_zensical.py`.

These are Chrome regressions, not a complete accessibility audit. They do not
replace screen-reader testing, visual contrast assessment, native mobile-browser
testing or the manual candidate checks in the support matrix. Narrow desktop
viewports alone do not qualify a mobile browser.

The demo check reads the explicit setup and preview commands from both READMEs
and requires the same dependency setup. Starting without generated files, it runs
the documented policy copy, rendering and landing-page/stylesheet copies before
checking the root page and all four collections. It exercises the policy tutorial,
preservation of edits across preview restarts and explicit restoration of the
example. Invalid policy edits must leave previously rendered pages intact.
The check also builds the documentation and checks all four embedded demo pages under
the repository subpath. Both sites reuse the instant-navigation and filter checks.
It also previews explicitly selected local group directories alongside Demo,
using only invented records. It checks reloading, multiple navigation sections,
loopback-only serving, exclusion of reports and unrelated files, and isolation
from subsequent ordinary previews and public builds. The local group pages run
the same browser interaction and accessibility checks as the synthetic demo.

The offline, browser and documentation CI jobs must pass before the release job
creates a draft release from a tag. The documentation job also supplies an
[HTML artifact for review](site.md#inspect-a-ci-build). All test data is invented;
these checks do not establish live CERN authentication. To preview the
documentation itself, use the [local site guide](site.md).

## Performance measurements

Use the public synthetic workload to compare changes on a recorded machine:

```bash
python tests/browser/check_performance.py --driver /path/to/chromedriver \
  --output /tmp/glance-performance.json
```

This uses the same dependencies as the browser checks. It generates 1,000 records
in each of four categories (4,000 total) in a temporary directory, then removes
the generated snapshot and site. It never reads the default working-directory
snapshot or retrieves data. The maintained four-record public demo supplies
repeated cohorts with unique native/public identifiers and remapped supersession
links. Each category retains its keyword, subgroup, date and status mix; one
quarter of each note collection is superseded. This measures scale with modest
record detail and repeated vocabulary, not the full diversity of a live registry.

The provisional review limits are **30 seconds per fresh CLI render** and
**500 milliseconds per filter action**. Three fresh subprocess renders include
Python startup, validation, preparation, all four Markdown pages, assets and the
report. Each uses a new destination; unchanged-output shortcuts do not apply.
Site generation is outside the render measurement, and OS caches are not cleared.

On each Zensical page, three rounds exercise half-match and zero-match searches,
category selection and resets. Browser-side time runs from a dispatched input
event or button activation through two animation frames, allowing a paint
opportunity. Expected visible-row counts and counters must agree. This excludes
WebDriver transport, physical typing and network latency; it is not an INP
measurement. Page readiness is reported separately without an acceptance limit.

Interactive ongoing cards let Chrome defer offscreen layout until those cards
approach the viewport. Filter timings therefore measure the visible response,
not completion of layout for every matching card. All records remain in the DOM;
the separate large-collection browser check covers distant-card navigation.
Static no-JavaScript pages and print media do not use this layout optimization.

The JSON report contains every timing sample, median and maximum, dataset hash
and sizes, source/benchmark fingerprints, OS, Python, dependency and browser
versions, and viewport. Any sample over a limit makes the command fail **after
writing the report**. Correctness or setup failures also fail the command but
may prevent report creation. The maximum is deliberately conservative; these
small samples do not establish a percentile or a public performance guarantee.

For a quick harness check use `--records 8 --repeats 1`; record counts must be
multiples of four. `--render-limit` and `--filter-limit` select explicit alternate
thresholds, recorded in the report. Compare equivalent datasets and environments,
inspect outliers and keep failed runs instead of silently loosening limits.
Run benchmarks alone, with other heavy jobs stopped.

The manual **Synthetic performance** GitHub Actions workflow runs the default
workload on Ubuntu and retains the JSON as an artifact, including timing failures.
It is separate from required PR checks while these limits are provisional.
Link the run and record its results for a release candidate; a local measurement
does not establish hosted-runner performance.

For version changes, artifact checks and the tag workflow, follow
[release qualification](releases.md). The [compatibility guide](compatibility.md)
defines the current interface boundaries; the [upgrade guide](upgrading.md)
describes how consumers can evaluate a candidate using saved data.
