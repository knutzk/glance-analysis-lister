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
[workflow guide](workflows.md#choose-where-to-start) gives the corresponding commands.

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

An analysis and its publications remain separate records. Analyses and papers
use `referenceCode`; notes use `temporaryReferenceCode`. A final public note
number is a display identifier, not a replacement for native identity. Equal
titles or similar identifiers do not establish a relationship.
The [data contract](curated-format.md) defines retained fields and preserves
the distinction between missing, null and empty values.

Preparation follows explicit links in both directions. A publication's
`relatedAnalysis` establishes its analysis association. An analysis-only
outbound link can supply linked-publication context, with an informational
diagnostic. If the publication points to a different analysis, preparation
reports the conflict rather than assigning it to both. A missing target remains
unresolved; it is not fabricated or silently matched by title.

Publications can appear without a resolved analysis link when their own policy
and lifecycle evidence qualifies them. Missing affiliations or search metadata
may use the publication's explicit analysis link, with the derivation recorded.
People remain those recorded on each resource in the current snapshot; they
are not reconstructed as historical membership. See the
[missing-link example](diagnostics.md#example-a-missing-link-does-not-exclude-a-published-paper)
for the effect on a rendered paper.

## Selection, lifecycle and browser filters

Three decisions determine what a reader sees:

1. **Group and policy selection:** ongoing analyses use main-group affiliation;
   publications use the group's configured policy. Policy criteria combine with
   OR, with distinct behaviour for missing and explicitly empty policies. The
   [policy reference](rendering.md#publication-policies) defines those rules.
2. **Lifecycle placement:** recognised ongoing analyses go on the ongoing page;
   uncertain analyses are listed separately. Publication tables contain selected
   submitted/published papers and released notes. A policy match alone does not
   establish submission or release. Linked publications inform analysis progress
   even when the publication policy excludes them from the archive.
3. **Browser filtering:** search, dates and status narrow the generated records.
   They do not change the registry, policy or diagnostic counts. Superseded
   released notes are retained in the output but hidden by the default filter.

For example, a submitted paper without a DOI can be included in the archive
under its **Under review** filter, while its linked analysis has completed active
review. That browser label tests for a DOI; it is not the lifecycle decision used
to determine archive eligibility. See [publication tables](publications.md).

Lifecycle rules use source statuses, recorded dates and explicit relationships.
Milestone ticks are evaluated independently: a later recorded step does not fill
in missing earlier dates. Unknown or contradictory evidence stays available in
the [diagnostic report](diagnostics.md). The preparation layer records decisions;
renderers display them without reclassifying source records.

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
from the failed stage using the [recovery guide](troubleshooting.md#resume-an-interrupted-workflow).

Generated files with identical bytes are left untouched, and unrelated output
files are retained. The [provenance guide](provenance.md) explains the input,
profile and generator fingerprints and the conditions for reproducible output.
