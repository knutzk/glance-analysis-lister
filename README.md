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

## Experimental API source registry

The standard installation includes stare. Run:

```bash
analysis-lister download-api --login --output json/glance_api_registry.json
```

Later runs can omit `--login` and reuse stare's credential storage. This uses
CERN browser SSO without Selenium, verifies TLS and disables response caching.
All accessible analyses, papers, CONF notes and PUB notes are downloaded
sequentially. Nested metadata and separate record identities are retained in a
versioned API source snapshot; unknown fields rejected by stare abort the run.
This is validated model output, not an unmodified HTTP-response archive.

The API source format is **not yet input to `render`, `build-registry` or
`export-obsidian`**. Use a separate destination from the CSV-derived registry.
The adapter does not yet map API statuses, missing title/link fields or curated
overrides into the existing view models. No private lookup files are needed
because this command does not construct an enriched view registry.

No file is published until all four resources pass pagination and identifier
checks. Existing API registries reject per-resource count drops greater than
20% unless `--allow-count-drop` is supplied. Credentials and private source
snapshots must not be committed.

## Console output

Normal output shows concise progress and a final summary. Diagnostics go to
stderr; command results and output paths go to stdout, so they can be redirected
separately. Coloured severity labels are enabled on terminals, and long notices
wrap with aligned continuation lines. Redirected output is plain text.

Use `--verbose` (`-v`) for timestamps, module names, per-file activity and query
details. `--quiet` (`-q`) keeps warnings, errors and the final results. Both flags
work before or after the command. Expected command failures omit tracebacks;
verbose mode includes them for troubleshooting.

```bash
analysis-lister refresh --verbose --csv-dir csv/all --snapshot json/all_registry.json
analysis-lister render --snapshot json/all_registry.json --quiet
analysis-lister --color never validate-lookups
```

`--color auto|always|never` controls colour independently for stdout and stderr.
Automatic colour respects `NO_COLOR` and `TERM=dumb`; `always` explicitly forces
it, including for redirected output. No extra terminal dependency is required.

## Retrieval configuration

`download` and `refresh` accept `--config PATH` for a TOML retrieval selection.
Without it, both use the bundled [unfiltered configuration](analysis_lister/configs/all.toml),
retrieving all accessible non-deleted ATLAS records. Group profiles remain
optional. The [TOPQ configuration](analysis_lister/configs/topq.toml) selects
records involving any of its three configured subgroups, including records
led by other groups.

```bash
analysis-lister refresh --config analysis_lister/configs/topq.toml \
  --csv-dir csv/topq --snapshot json/topq_registry.json
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
before use. This release does not discover groups or retrieve clone
relationships, and does not claim to provide a verified leading-group query
preset.

Downloads store `retrieval_scope.json` alongside CSVs. Registry builds carry
that selection into the snapshot. Existing destinations with a different
selection are rejected, even with `--allow-count-drop`; use separate CSV and
snapshot destinations for different datasets. Existing CSV batches, snapshots
or saved HTML without scope metadata cannot be used for refresh: retrieve into
fresh destinations. No group selection is inferred from old data. Changing a
scope's display name or reordering its values does not create a new selection.

`--save-html DIR` saves full responses, including result counters, plus scope
metadata; CSVs retain their selected columns. With `--from-html DIR`, scope
metadata must be present and match. Offline replay validates the saved result
counters exactly as a live download does; it does not apply server-side
filters to saved records. Older table-only HTML must be downloaded again.

These options configure retrieval only. Rendering and Obsidian export retain
their existing TOPQ presentation assumptions.

Unfiltered retrieval is the default, so no configuration flag is needed:

```bash
analysis-lister refresh --csv-dir csv/all --snapshot json/all_registry.json
```

This profile uses `name = "ATLAS"` and `all = true` without a `[selection]`
table. An explicit custom configuration still cannot contain an empty selection.

Every table must include GLANCE’s `Showing 1 to N of N results` counter, and the
parsed CSV row count must equal the reported total. Missing or conflicting
counters, partial pages and truncated responses abort the entire batch before
publication. Pagination is detected and rejected rather than silently storing
one page. `--allow-count-drop` cannot bypass this check. Completeness is checked
against the total GLANCE reports for the authenticated user and requested scope.

## Publication matching

Papers, CONF notes and PUB notes enrich an analysis only when their reference-code suffix
and nonempty short title both match exactly. Unmatched paper rows do not enrich
an analysis; unmatched CONF rows likewise remain unattached. PUB notes without a match are retained independently
under their full `PUB-...` identifier, using their own metadata and publication
status. They do not acquire an ANA link or appear as ongoing analyses.

Building from CSV requires short titles for papers and CONF/PUB notes, plus
PUB descriptive metadata. Older minimal note CSV exports must be downloaded
again before rebuilding the registry.
Existing JSON snapshots remain readable.

## Ignored analyses

`analysis_lister/lookup_dicts/ignored_analyses.py` lists reviewed exceptions with
reasons. These analysis identifiers stay in snapshots but are excluded from
output views, view counts and unmatched-record warnings. This does not alter
GLANCE statuses or create publication links. Independent PUB records retain
their own identifiers and are unaffected by an ignored ANA identifier.

## Clone relationships

Maintain verified clone and duplicate origins in `analysis_lister/lookup_dicts/clones.py`.
`Clones` maps each clone's analysis reference to its original analysis reference;
multiple clones can share an origin. Add a `# Source:` or `# Reason:` comment
immediately above every entry. Validate changes with `analysis-lister validate-lookups`.

Clone exclusions are calculated in memory from this dictionary whenever a
registry is loaded. No clone fields or exclusion flags are stored in JSON.
Dictionary changes therefore apply to existing snapshots, without downloading
new data.

A paper supersedes CONF entries on its ancestor chain, including during paper
review. Closed or unstarted papers do not supersede them. Distinct sibling
publications and active analyses remain visible. Known finished clone-family
records without an attached publication are omitted. All records and original
GLANCE states remain in JSON. Missing descendants do not supersede CONF notes,
and cycles are rejected. Normal publication date cuts still apply.

## Try the synthetic example

From a checkout, render the included example without CERN access:

```bash
analysis-lister render --snapshot examples/synthetic_registry.json \
  --output-dir pages
```

This writes 13 Markdown pages under `pages/`. All four records, names, titles,
dates and publication links are invented. The `DEMO` reference codes do not
identify real analyses. See [the example notes](examples/README.md).

## Obsidian export

```bash
analysis-lister export-obsidian --snapshot examples/synthetic_registry.json \
  --output-dir obsidian_output
```

The exporter writes papers to `obs_published/` and ongoing analyses to
`obs_ongoing/` under the chosen destination. The example produces one note in
each directory. CONF and PUB notes are included in the site pages, but are not
exported as separate Obsidian notes. Existing notes that this run did not write
are reported as stale and left in place.

For your own data, supply your snapshot.
The default destination is `obsidian_output/`.

## Maintained analysis relationships

Titles come directly from GLANCE’s Short Title, Public Short Title and Full
Title fields. The only maintained analysis dictionary is
`analysis_lister/lookup_dicts/clones.py`, which covers clone and duplicate
origins. Citation metadata lives in `json/doi_metadata.json`. No private Python
lookup overrides are supported; select a different JSON citation store with
`--doi-cache` when needed. Validate maintained data with
`analysis-lister validate-lookups`.

## DOI citation resolution

The single citation dictionary is [json/doi_metadata.json](json/doi_metadata.json).
It is versioned in Git, with one complete DOI entry per line for readable diffs.
The wheel and source distribution include the same dictionary. There is no
separate maintained Python citation dictionary and no merging of seed entries.

Each record requires `citation` and `source`. Protection follows the source:
`manual` citations are never replaced automatically; inferred and INSPIRE
citations can be refreshed explicitly. To protect an edited citation, set its
source to `manual`. There is no separate `locked` field. Older stores containing
that field remain readable, but it is ignored and removed on writing.
`material` is stored only when the publication/correction role is known.

All commands read the dictionary offline. `--doi-cache PATH` selects a separate
store; a missing custom store starts empty. When working outside a checkout,
the default path uses the packaged copy until a working-directory store is
written. Only `resolve-dois` can make INSPIRE requests.

INSPIRE's compact journal abbreviations are formatted consistently with the
existing citations, for example `Phys.Rev.D` → `Phys. Rev. D`. After an update
that used an older formatter has finished, fix stored non-manual citations
without repeating network lookups:

```bash
analysis-lister format-citations
```

This also shortens page ranges to the starting page, for example `101–120` →
`101`. New INSPIRE resolutions use the same convention. Citation provenance,
correction prefixes, dates and individual article numbers are retained.
Manual citations are unchanged. Unknown journal abbreviations are
retained rather than guessed. Do not run it while a resolver is writing the
same JSON file.

First infer citations without network access:

```bash
analysis-lister resolve-dois --snapshot json/all_registry.json --method infer
```

The initial rule recognises complete JHEP DOIs, for example
`10.1007/JHEP07(2023)203` → `JHEP 07 (2023) 203`. It records
`source = "doi-pattern:jhep"`; no `material` field is written:
the DOI identifies the citation components, but not whether it is a correction.

Then retrieve remaining missing citations from INSPIRE:

```bash
analysis-lister resolve-dois --snapshot json/all_registry.json --method inspire
```

Alternatively, `--method auto` tries inference before INSPIRE. Inference is the
default. Existing entries are skipped; `--refresh-existing` revisits only
non-manual entries. To enrich inferred citations with correction metadata, run
`--method inspire --refresh-existing`. Manual entries are never replaced.
`--limit 10` bounds the number of entries attempted in a run. Individual DOIs
can be supplied using repeated `--doi` arguments instead of `--snapshot`.

Successful results include provenance and resolution timestamps and are saved
atomically after each entry. Failed requests, missing records, incomplete
citations and ambiguous DOI/publication associations remain retryable; failed
refreshes retain the previous citation. INSPIRE lookups match the requested DOI
and material to publication information, and label verified errata/addenda.
DOI ordering uses cached publication/correction labels and dates encoded in
DOIs. Ambiguous cases retain input order with a warning; no manual order
dictionary is maintained.
Duplicate publication rows are combined only when their structured citation
fields agree; compatible partial rows can fill missing fields. Conflicting
metadata remains unresolved. An unlabelled DOI can inherit an explicit label
from another occurrence of that same DOI, or a unique remaining material when
exactly one DOI and one publication material remain unmatched.

INSPIRE requests use a separate session without GLANCE cookies, verified TLS,
bounded timeouts and retries, and rate limiting. A server-requested pause over
60 seconds is deferred to a later run. No titles or analysis identifiers are
sent to INSPIRE, only DOIs. See the
[INSPIRE API documentation](https://github.com/inspirehep/rest-api-doc) and
[publication metadata schema](https://github.com/inspirehep/inspire-schemas/blob/master/inspire_schemas/records/hep.yml).

Subsequent `render`, `build-registry`, `refresh` and `export-obsidian` operations
use the cached citations. The resolver does not rewrite registry snapshots;
citation fields are reconstructed when a snapshot is loaded. Review and commit
citation updates as normal data changes. Only this citation JSON and the
synthetic example JSON are permitted public JSON files; private registries,
cookies and other generated JSON remain ignored. Run resolution and operations
that edit the same dictionary sequentially.

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
