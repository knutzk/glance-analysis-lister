# glance-analysis-lister

Python 3.13 tools for maintaining ATLAS GLANCE analysis registries and generating
Markdown pages for the Top Working Group.

## Install

**Recommended for running the tool:** use Python 3.13, create a virtual
environment, and install with pip. Run these commands from the repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
analysis-lister --help
```

This installs the tool and dependencies for all commands, including downloads
and interactive CERN login. Activate the environment again with
`source .venv/bin/activate` when opening a new terminal.

After pulling code updates, update the installation in the active environment:

```bash
python -m pip install --upgrade -r requirements.txt
```

The `.[download]` line inside `requirements.txt` is pip syntax: `.` means this
local package, and `[download]` selects its optional download/login dependencies.
Pip reads the dependency declarations from `pyproject.toml`. Any `.egg-info/`
directory created during installation is generated metadata; leave it to pip.

## Use

Run commands from the directory containing your private inputs and desired
output. All data paths are relative to the working directory. The package
includes no registry, downloaded GLANCE data, or private analysis titles.

```bash
analysis-lister --help
analysis-lister refresh --login --csv-dir csv --snapshot json/glance_registry.json
analysis-lister render --snapshot json/glance_registry.json --output-dir pages
analysis-lister validate-lookups --snapshot json/glance_registry.json
```

`python -m analysis_lister` provides the same commands. `download` refreshes only
the CSV tables; `build-registry` constructs a registry from existing CSVs.
Each command has `--help`. Interactive CERN login requires Chrome and a terminal.
Rendering uses a local snapshot and requires no login.

Markdown pages are written to `pages/` by default. Use `--output-dir` to choose
a different destination. Obsidian export defaults to `obsidian_output/`.

Refresh stages all four tables, validates the candidate registry and promotes
CSVs with rollback before atomically replacing JSON. Drops greater than 20% are
rejected; `--allow-count-drop` overrides only that guard. Run refresh and registry
build operations sequentially.

## Retrieval configuration

`download` and `refresh` accept `--config PATH` for a TOML retrieval selection.
Without it, both use the bundled [TOPQ configuration](analysis_lister/configs/topq.toml),
which preserves the original selection exactly: records involving any of the
three selected TOPQ subgroups, including records led by other groups.

```bash
analysis-lister refresh --config analysis_lister/configs/topq.toml \
  --csv-dir csv --snapshot json/glance_registry.json
```

The bundled [HIGP configuration](analysis_lister/configs/higp.toml) selects
subgroups 824, 825, 826, 827, 828, 831, 830 and 829. Use separate destinations:

```bash
analysis-lister refresh --config analysis_lister/configs/higp.toml \
  --csv-dir csv/higp --snapshot json/higp_registry.json
```

The configuration specifies GLANCE query values directly; it does not infer
group membership from subgroup names or maintain an organisational hierarchy:

```toml
name = "TOPQ"

[selection]
field = "subgroups"
operator = "contains"
values = [80, 198, 205]
```

Each value becomes an indexed GLANCE filter clause, as in the original query.
Selections must contain at least one positive integer ID or nonempty string;
duplicate values are removed. Unknown configuration keys are rejected. The
field and operator are GLANCE's query identifiers, not display column labels.
The bundled subgroup query is verified against the previous implementation;
other fields, operators and group IDs must be obtained from GLANCE and verified
before use. This release does not discover groups or resolve clones, and does
not claim to provide a verified leading-group query preset.

Downloads store `retrieval_scope.json` alongside CSVs. Registry builds carry
that selection into the snapshot. Existing destinations with a different
selection are rejected, even with `--allow-count-drop`; use separate CSV and
snapshot destinations for different datasets. Old datasets without scope
metadata remain compatible with the default TOPQ selection only. Changing a
scope's display name or reordering its values does not create a new selection.

`--save-html DIR` saves the full returned table columns and scope metadata;
the CSVs retain their existing column selection. With `--from-html DIR`, the
saved scope must match when metadata is present. For older HTML without
metadata, the configuration you supply declares its scope; offline replay
does not apply server-side filters to saved records.

These options configure retrieval only. Rendering and Obsidian export retain
their existing TOPQ presentation assumptions.

## Try the synthetic example

From a checkout, render the included example without CERN access:

```bash
analysis-lister render --snapshot examples/synthetic_registry.json \
  --lookup-dir examples/lookups --output-dir pages
```

This writes 13 Markdown pages under `pages/`. All four records, names, titles,
dates and publication links are invented. The `DEMO` reference codes do not
identify real analyses. See [the example notes](examples/README.md).

## Obsidian export

```bash
analysis-lister export-obsidian --snapshot examples/synthetic_registry.json \
  --lookup-dir examples/lookups --output-dir obsidian_output
```

The exporter writes papers to `obs_published/` and ongoing analyses to
`obs_ongoing/` under the chosen destination. The example produces one note in
each directory. CONF and PUB notes are included in the site pages, but are not
exported as separate Obsidian notes. Existing notes that this run did not write
are reported as stale and left in place.

For your own data, supply your snapshot and optional private lookup directory.
The default destination is `obsidian_output/`.

## Private lookup dictionaries

The package includes public DOI references and empty short-title defaults.
To supply your own titles and overrides, keep these four literal dictionaries
in a separate local directory:

| File | Dictionary |
| --- | --- |
| `short_titles.py` | `ShortTitles` |
| `journal_refs.py` | `JournalRefs` |
| `known_duplicates.py` | `KnownDuplicates` |
| `doi_order.py` | `DoiOrder` |

Each file must define its dictionary as a literal; empty dictionaries are valid.
For example, `short_titles.py` can contain:

```python
ShortTitles = {}
```

Supply the directory with `--lookup-dir`:

```bash
analysis-lister render --snapshot json/glance_registry.json \
  --output-dir pages --lookup-dir /path/to/private/lookups
```

The files are parsed and validated without executing Python. Their dictionaries
replace the package defaults for that operation. Without this option, rendering
uses the public defaults and titles from the supplied snapshot. Keep credentials,
registry snapshots, downloaded tables, private lookups and generated pages out of
this repository.

## TLS

Downloads verify certificates and hostnames. The wheel includes the public
Sectigo intermediate certificate required by GLANCE; see
[certificate provenance](analysis_lister/certs/README.md).
`REQUESTS_CA_BUNDLE`, then `CURL_CA_BUNDLE`, can replace the trust bundle.

## Development

With the virtual environment from the installation section active, install the
**development requirements**:

```bash
python -m pip install -r requirements-dev.txt
```

This includes `-e .[dev]`, so it also installs the package in **editable mode**:
source changes take effect immediately. It includes the runtime dependencies,
download support and development tools; you do not need to install both
requirements files. Rerun the command after changing dependencies or package
metadata.

Run the checks with:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python -m build
```

GitHub CI runs these checks on Python 3.13 for pushes and pull requests. It also
installs the built wheel in a clean environment and checks the CLI, synthetic
page rendering, bundled certificate, and licence files. CI requires no CERN
credentials or private analysis data.

Tests use synthetic records and do not establish that live authentication works.
Use local snapshots to test rendering changes. Preserve GLANCE's exact padded
status strings, DOI/erratum alignment and unique subgroup anchors. Validate
maintained lookups after changing them.

## Releases

For each release, update the version in `pyproject.toml` and add release notes
in `.github/release-notes/vX.Y.Z.txt`. Commit and push those changes, wait for CI,
then create and push an annotated `vX.Y.Z` tag on the verified commit.

Tag CI checks the version and notes, runs the normal checks, builds and verifies
the distributions, and creates a draft GitHub Release with the wheel and source
archive attached. Review the workflow log and draft before publishing it.
The release job alone has repository write permission. PyPI publishing is not
configured. Never move a published version tag; issue a new version for fixes.

## Licence and contact

Copyright © 2024–2026 Knut Zoch. The software is licensed under
[GNU GPL version 3](LICENCE) (`GPL-3.0-only`), without warranty.
You may use, modify and redistribute it, including commercially. When
redistributing the software or modified versions, preserve the copyright and
licence notices, provide the corresponding source as required by GPLv3, and
keep the covered work under GPLv3. Private modifications need not be published.

This licence covers the software; it grants no rights to private GLANCE data.
The bundled Sectigo certificate is a third-party artifact, whose issuer and
provenance are documented [separately](analysis_lister/certs/README.md).

Maintainer: [Knut Zoch](https://github.com/knutzk).
