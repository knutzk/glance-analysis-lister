# Package architecture

[Documentation index](README.md)

Retrieval produces a validated API snapshot. Curation selects and enriches its
fields into a registry. View preparation applies membership, publication and
lifecycle rules; rendering turns those prepared collections into pages and
reports. Each stage can consume saved output from the preceding stage.

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

Records keep their native identities and explicit relationships. Validation
checks structural correctness; it does not guess associations, reconstruct
history or repair source chronology. See the [data contract](curated-format.md)
for those boundaries and [workflow recovery](workflows.md#validation-and-recovery)
for file-publication guarantees.
