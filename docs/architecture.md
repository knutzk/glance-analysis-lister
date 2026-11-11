# Package architecture

[Documentation index](README.md)

Retrieval produces a validated API snapshot. Curation selects and enriches its
fields into a registry. View preparation applies membership, publication and
lifecycle rules; rendering turns those prepared collections into pages and
reports. Downloading, building and rendering have separate saved-file boundaries;
prepared views are in-memory values.

## Data flow and boundaries

| Stage | Input | Result and responsibility |
| --- | --- | --- |
| API retrieval | GLANCE through an authenticated stare client | A validated snapshot of all accessible records, before group selection. |
| Registry construction | Saved API snapshot and identifier/citation dictionaries | A curated v2 registry containing every record with adopted fields and recorded enrichment. No network access. |
| View preparation | Validated curated registry and a group profile | Independent analysis/publication collections with selection, lifecycle and diagnostic evidence. No rendering or external lookup. |
| Rendering | Prepared collections and provenance | Four Markdown pages, shared assets and a diagnostic report. The CLI writes these to disk; the consuming site builds HTML. |

The registry reader validates and returns copies. Loading a registry does not
repeat enrichment, update citations or apply a publication policy. Rebuild from
the API snapshot when curation inputs change; rerender the curated registry when
only the group, policy or presentation changes. The
[workflow guide](data.md#choose-where-to-start) gives the corresponding commands.

HTML retrieval is a separate route to standalone CSV exports. Those exports are
not inputs to registry construction. Citation resolution is also separate:
public INSPIRE requests do not use GLANCE credentials, and their results enter
pages only after rebuilding the registry with the updated citation store.

## Code layout

Paths below are relative to the repository root.

| Area | Responsibility |
| --- | --- |
| `analysis_lister/cli.py` | Parse, validate and dispatch commands. |
| `analysis_lister/refresh.py` | Check destinations and coordinate download, build and render stages. |
| `analysis_lister/downloaders/` | API retrieval and independent HTML-to-CSV export, including authentication, validation and file publication. |
| `analysis_lister/registry/` | Enrichment, schema validation, field retention, identifiers, snapshot comparison and registry reading. |
| `analysis_lister/citations/` | Citation storage, formatting, ordering, INSPIRE retrieval and resolution. |
| `analysis_lister/views/` | Policies, prepared collections, relationships, diagnostics, renderers and browser assets. |
| `analysis_lister/storage.py` | Atomic file replacement. |
| `analysis_lister/provenance.py` | Source revisions and content fingerprints. |
| `tests/browser/` | Synthetic standalone and Zensical integration checks. |
| `scripts/` | Distribution validation, documentation builds and screenshot capture. |

## View preparation and rendering

Within `views/`, `analysis_states.py` and `publication_states.py` define lifecycle
and milestone rules. Preparation uses those rules without importing renderers,
so [prepared collections](python-access.md#prepare-a-group-view) are also usable
in Python applications.

Markdown rendering consumes prepared records and page controls. `people.py`
shares board/chair formatting. `diagnostics.py` classifies issues and their
effects; `report.py` records the decisions and evidence.

## Independent records and relationships

The user-facing relationship and identifier rules are explained in the data guide.

[Relationships between records](data.md#relationships-between-records)

## Selection, lifecycle and browser filters

Membership, publication selection and lifecycle decisions belong to view preparation.
Browser filtering operates on its rendered result. Keep these responsibilities
separate when extending the package.

[Selection rules](selection.md)

## File replacement and recovery

Validation and replacement operate at different scopes:

| Operation | Before replacement | Failure boundary |
| --- | --- | --- |
| API download or registry build | Validate the complete candidate; check the existing destination's endpoint and per-resource count drops. | Each JSON file is replaced atomically. A failed candidate does not replace the previous snapshot. |
| Group rendering | Validate the registry, prepare collections and render all documents in memory. | Replace each changed file atomically; a write failure can leave a mixture of old and new files. There is no directory-wide transaction. |
| HTML export | Stage and validate all four CSV tables and their manifest. | Back up and replace the batch, attempting rollback on failure. An interruption marker and retained recovery paths identify an incomplete batch. |
| Refresh | Check configuration and destination collisions before authentication. | Download, build and render sequentially; stop on the first failure and retain completed stages. There is no workflow-wide rollback. |

Atomic replacement prevents a reader from seeing a partially written individual
file; it does not coordinate concurrent writers or guarantee a consistent set
of files across stages. Run operations sharing destinations sequentially. Retry
from the failed stage using the [recovery guide](problems.md#resume-an-interrupted-workflow).

Generated files with identical bytes are left untouched, and unrelated output
files are retained. The [provenance guide](data.md#trace-your-output) explains the input,
profile and generator fingerprints and the conditions for reproducible output.

## Curation implementation

`registry/enrichment.py` contains transformation rules. Its `STRING_LIST_FIELDS`
converts selected named-object collections to names or string lists. Added or
reshaped fields use the `gal_` prefix; source keys are removed after enrichment.
`registry/fields.py` then selects domain fields, including nested relationships,
metadata and DOI/citation entries. DOI/citation pairs stay aligned with their
corrections.

New API fields are excluded until explicitly adopted into the data contract,
independently of any view. The registry retains snapshot and build metadata,
identifier evidence and dictionary hashes for provenance and safe replacement.
For a worked example across these layers, see the
[contributor field walkthrough](contributing-field.md).

The bundled schema validates nested types and dates; separate checks enforce
counts and unique identifiers. Only curated v2 is supported. See the contract's
[compatibility policy](curated-format.md#compatibility-policy) for optional
additions, breaking changes and frozen fixtures.
