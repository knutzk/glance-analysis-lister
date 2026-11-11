# Contributing

Contributions can improve the selection rules, citation handling, generated pages
or documentation. Start by describing the behaviour you want to change and a
small example of the expected result. The [topic guides](README.md) explain the
existing behaviour; this page covers where to make a change and how to check it.

Use independently invented records in examples, tests and bug reports. Never
attach private GLANCE snapshots, cookies, downloaded HTML or unpublished analysis
information. Public citation metadata is fine when its source is recorded.

## Set up a checkout

Use Python 3.13, matching CI. From the repository root:

```bash
# Create the development environment and install the editable package.
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Reinstall after changing dependencies or package metadata. The
[synthetic demo](../examples/README.md) provides a complete offline example for
trying changes without CERN access.

## Find the right part of the code

| Area | Responsibility |
| --- | --- |
| `analysis_lister/cli.py`, `refresh.py` | Command validation and sequential workflow orchestration. |
| `analysis_lister/downloaders/` | API retrieval and independent HTML/CSV export; authentication and download validation. |
| `analysis_lister/registry/` | Field retention, enrichment, identifiers, validation, reading and snapshot comparison. |
| `analysis_lister/citations/` | Citation stores, formatting, ordering and public metadata retrieval. |
| `analysis_lister/views/` | Policies, lifecycle rules, prepared collections, diagnostics, rendering and browser assets. |
| `analysis_lister/storage.py`, `provenance.py` | Safe file replacement and input/code fingerprints. |

Keep the saved-file boundaries described in the [data guide](data.md).
Registry reads validate and return copies; they must not enrich data or request
it over the network. Preparation applies selection and lifecycle rules without
rendering, so the same collections remain usable through the Python API.
Renderers consume those prepared values. HTML exports remain independent of the
API-to-registry workflow.

For a new source field, decide its meaning, missing/null/empty behaviour and
which resources need it. Update enrichment where necessary, the retention list
in `registry/fields.py` and the bundled schema together. Then expose it through
prepared data and rendering only where useful. An available field does not
necessarily need a browser filter. Preserve native identities, explicit
relationships and aligned DOI/citation pairs.

File-writing changes must preserve the documented [recovery behaviour](problems.md#resume-an-interrupted-workflow).
JSON replacement is atomic per file; rendering and refresh have no whole-workflow
rollback. Do not introduce simultaneous writers to shared destinations.

## Check a change

Run the offline suite and style checks from the repository root:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
git diff --check
```

Use `tests/view_fixtures.py` for invented records and add focused regressions
that show the changed behaviour. Keep historical fixtures when they test inputs
we still support, or use them to check that unsupported files fail clearly. Add
fixtures for new formats and features; do not rewrite old evidence just to make
a failing check pass. Generated JSON does not require indefinite backward
compatibility or migration tooling.

When changing a stored format, keep the validation schema aligned with the reader.
Malformed or wrong-format inputs should fail with useful recovery instructions.
Generator metadata is advisory: missing or different code fingerprints must warn
without rejecting otherwise valid data. Do not reintroduce numeric schema-version
gates. Keep the fingerprint independent of worktree locations and documentation.
Explain when users need to rebuild from an API snapshot or obtain a fresh download. Treat custom citation stores
separately: a format change must account for user edits and their provenance.

| Change | Useful checks |
| --- | --- |
| Enrichment or retained fields | `test_curated_registry.py`, `test_registry_fields.py`, `test_retained_field_contract.py`. |
| Stored data or reader | `test_registry_contract.py`, `test_curated_reader.py`. |
| Policies, relationships or lifecycle | `test_publication_curation.py`, `test_view_preparation.py`, `test_view_contracts.py`. |
| CLI, failure handling or storage | `test_workflow_cli.py`, `test_download_errors.py`, `test_refresh_recovery.py`, storage tests. |
| Generated output or links | Rendering tests, `test_generated_contract.py`, `test_render_reproducibility.py`, relevant browser checks. |

For example, `python -m unittest discover -s tests -p 'test_registry_fields.py' -v`
runs just the field-retention tests. Include the full checks and any limitations
in the pull request, together with the problem and resulting behaviour.

### Python test coverage

CI measures line and branch coverage of the maintained Python package while
running the offline suite, including its child Python processes. It publishes
separate line/branch totals in the job summary and a `python-coverage` artifact
with HTML, XML and JSON reports. Coverage currently informs review; no percentage
threshold is enforced. A failing test run produces partial coverage only.

To reproduce the report, use a clean checkout without local experimental tests
and run from the repository root after installing the development dependencies:

```bash
python -m coverage erase
python -m coverage run -m unittest discover -s tests -v
python -m coverage combine
python -m coverage report
python -m coverage html
python -m coverage xml
python -m coverage json
```

Open `coverage-report/html/index.html` to inspect missing lines and branches.
The report includes maintained package modules even if tests never import them;
experimental Events modules are excluded. Tests and third-party dependencies
are outside the measured source scope. The terminal report's percentage combines
line and branch opportunities; the JSON report and CI summary also show them
separately. Run these commands sequentially; erase old measurements before each
fresh run so stale subprocess data cannot inflate the result.

Python coverage does not measure browser JavaScript, the separate browser/site
checks or live authentication. Execution alone does not prove correctness:
prioritise missing failure/recovery paths and domain decisions when adding tests.
Run performance benchmarks separately, without coverage instrumentation.

### Browser and site checks

For changes to controls, assets or site integration, install Chrome, a matching
ChromeDriver and the browser requirements. Supply the driver explicitly;
`CHROME_BINARY` can select a nondefault Chrome executable.

```bash
python -m pip install -r tests/browser/requirements.txt
python tests/browser/check_ongoing.py --driver /path/to/chromedriver
python tests/browser/check_papers.py --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource confnotes --driver /path/to/chromedriver
python tests/browser/check_notes.py --resource pubnotes --driver /path/to/chromedriver
python tests/browser/check_zensical.py --driver /path/to/chromedriver
python tests/browser/check_demo.py --driver /path/to/chromedriver
```

These checks cover synthetic pages, keyboard interaction, narrow layouts,
light/dark themes, saved links, instant navigation and no-JavaScript content.
The demo check also exercises the documented setup and local group previews.
They use invented data and do not establish live CERN access.

For performance-sensitive changes, run the separate synthetic benchmark:

```bash
python tests/browser/check_performance.py --driver /path/to/chromedriver \
  --output /tmp/glance-performance.json
```

The default workload has 1,000 records per category. Its provisional review limits
are 30 seconds per fresh render and 500 ms per filter action, not a public speed
guarantee. Run it alone, record the environment and retain failed samples.
The manual **Synthetic performance** workflow provides an Ubuntu comparison.

### Documentation changes

Edit the README or guide source, then preview or build the documentation:

```bash
python -m pip install -r requirements-docs.txt
python scripts/docs.py serve
```

Open `http://127.0.0.1:8000/glance-analysis-lister/`; stop with **Ctrl+C**.
For the strict build, run `python scripts/docs.py build`. New pages need an entry
in `scripts/docs.py`'s public input list and `zensical.toml` navigation. Restart
the preview after adding a page or changing renderer code. Edit source files,
not generated `site-src/` or `site/`; run one build or preview at a time.

CI uploads a `documentation-site` artifact for review. It contains only public
guides and synthetic examples. To inspect it under the configured URL prefix,
extract it into `preview/glance-analysis-lister/` and run
`python -m http.server 8000 --bind 127.0.0.1 --directory preview`.

## Prepare a release

Choose the exact commit and package version together. Review user-visible and
bundled-data changes against the [upgrade policy](upgrading.md#what-can-change),
update `pyproject.toml`, and write `.github/release-notes/vVERSION.txt`.
Notes should explain changes, migration steps and known limitations; avoid a
catalogue of implementation work. Keep historical notes as release records.

Use a clean checkout with no private inputs or experimental files. After the
offline, browser and strict documentation checks, build the source archive and
the wheel from it:

```bash
python -m build
```

Use a fresh output directory so the artifacts belong to this candidate. Install
the actual wheel into a new environment outside the checkout, replacing `VERSION`
and the environment path as needed:

```bash
python3.13 -m venv /tmp/glance-release-check
/tmp/glance-release-check/bin/python -m pip install dist/glance_analysis_lister-VERSION-py3-none-any.whl
/tmp/glance-release-check/bin/python -m pip check
/tmp/glance-release-check/bin/python -I scripts/check_distribution.py
```

Inspect both distributions and build the documentation from an unpacked source
archive. The archive includes the guides and examples; the wheel includes runtime
schemas, assets, dictionaries, policies, certificates and licences. Neither may
contain private data. Test the [upgrade procedure](upgrading.md) and the actual
consuming site's theme and navigation before replacing a working installation.

Record the candidate commit, artifact hashes, dependency and browser versions,
commands/results, performance report and skipped checks. CI covers Python 3.13
on Ubuntu with Chrome and the pinned Zensical default theme; repeat candidate
checks on macOS. Other Python versions, operating systems, browsers and custom
themes need their own evidence. Desktop narrow-view tests are not mobile-browser
qualification, and synthetic recovery tests do not establish power-loss or
concurrent-writer safety. Live login and downloads require separate authorised
checks; record only non-sensitive outcomes.

A pushed `vVERSION` tag must match package metadata and have nonempty notes.
After the package, browser and documentation jobs pass, CI creates a **draft
GitHub release** containing the tested distributions and notes. Review it before
publication; CI does not upload to a package index. The separate Pages workflow
publishes the development documentation from `main`.

There is one development documentation site. Release tags and source archives
retain the matching guides and demo; there is no hosted version selector.
The pinned Zensical version does not lock every dependency or guarantee identical
HTML when rebuilding later. Short-lived CI artifacts are review aids, not a
permanent release archive.
