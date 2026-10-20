# glance-analysis-lister

Python 3.13 tools for maintaining ATLAS GLANCE analysis registries and generating
Markdown pages for the Top Working Group.

## Install

From a checkout of this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# For an editable installation with development tools:
python -m pip install -r requirements-dev.txt
```

`requirements.txt` installs support for all commands, including downloads and
interactive CERN login. For rendering only, use `python -m pip install .`.
Dependency declarations live in `pyproject.toml`; the requirements files select
the appropriate package extras.

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

Refresh stages all four tables, validates the candidate registry and promotes
CSVs with rollback before atomically replacing JSON. Drops greater than 20% are
rejected; `--allow-count-drop` overrides only that guard. Run refresh and registry
build operations sequentially.

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

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python -m build
```

Tests use synthetic records and do not establish that live authentication works.
Use local snapshots to test rendering changes. Preserve GLANCE's exact padded
status strings, DOI/erratum alignment and unique subgroup anchors. Validate
maintained lookups after changing them.

The `create_obsidian_output.py` helper provides a manual Obsidian exporter;
its output and snapshot paths are configured at the top of the script.

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
