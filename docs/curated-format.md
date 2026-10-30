<!-- SPDX-FileCopyrightText: 2024-2026 Knut Zoch -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Curated registry contract

The curated JSON is a reusable domain dataset, independent of GLANCE API models,
publication policies, Markdown renderers and the events list. Curation adapts
upstream data to this contract; an API change must not silently change the
meaning or type of an existing curated field.

Version 2 is defined by the bundled
[`curated-v2.schema.json`](../analysis_lister/registry/schemas/curated-v2.schema.json)
(JSON Schema Draft 2020-12) and the semantics below. The existing layout and names
are retained. Validation does not insert defaults, reconstruct history, merge
records or filter by group.

## Compatibility policy

- `schema` is `glance-curated-registry`; `schema_version` is the integer `2`.
  This version is independent of the Python package and upstream API versions.
- Adding optional fields is compatible within v2. Readers accept unknown fields,
  including nested fields, and their absence. Status, journal and group codes
  remain open strings.
- Removing or renaming a field, narrowing its accepted type, making an optional
  field required, or changing its meaning requires a new schema version.
  Changing which records are retained requires an explicit compatibility review.
- Do not remove fields simply because a view stops using them. Field selection
  in `registry/fields.py` must remain aligned with the schema; contract tests
  check this independently of renderers.
- Only v2 is supported today. Older and future versions fail clearly. A future
  breaking version must define supported input versions and explicit, tested
  migrations before readers accept those inputs. Migrations must not invent
  missing historical information.
- Fixtures in `tests/fixtures/curated` are independently invented public records,
  frozen when introduced. Do not rewrite them to match a new writer. Add another
  fixture for a new feature and keep existing fixtures readable.

This first schema formalizes intended v2 types that were previously only partly
checked. Malformed known fields now fail earlier, at load/build time, with a field
path. This tightening is intentional; valid saved registries need no rewriting.

## Container, identity and relationships

The four resource arrays (`analyses`, `papers`, `confnotes`, `pubnotes`) and their
nonnegative integer `counts` are required. Empty arrays with zero counts are valid
storage. Download completeness and replacement count-drop protection are separate
safeguards and remain unchanged.

Analyses and papers use `referenceCode`; notes use `temporaryReferenceCode`.
Native identifiers are nonempty and unique within their resource. Public note
identifiers (`finalReferenceCode`, `gal_finalReferenceCode`) do not replace native
identity. Readers preserve array order; consumers should identify records by ID.

`relatedAnalysis` is a relationship object or null. `relatedPublications` and
note `supersededBy` are arrays of relationship objects, or null. Objects retain
source `type` and `referenceCode`; missing/null values represent incomplete source
evidence. Relationships do not imply merging or reciprocal links. Missing targets
are allowed. `resolve_link` requires a known type and nonempty native reference,
returns `None` for a missing target, and rejects unsupported link types.
Reading and validation never look up records over the network.

## Values and dates

Missing keys mean information was not retained or supplied; null means an
explicitly absent value. Neither proves that an event has or has not happened.
Empty arrays mean no entries in the supplied collection. The reader inserts no
defaults and preserves missing, null and empty values. Optional phase, metadata
and documentation objects can be null.

`gal_analysisContacts` and `gal_contactEditors` are required arrays of names.
Optional board, reader and sign-off roles accept a string, string array or null
for compatibility with existing v2 consumers; the writer emits arrays for boards
and readers. Optional derived metadata lists also accept null. People describe the snapshot, not necessarily the
membership at a historical assignment date. Raw `analysisTeam` is prohibited.

Milestone values retain a calendar date (`YYYY-MM-DD`) or an RFC 3339 timestamp
with timezone; null and empty source strings mean no date. Derived
`gal_*MeetingDates` contain calendar dates only. Validation checks actual dates
and timestamps but does not order milestones or infer missing events. Source
chronology errors should be corrected in GLANCE, not silently repaired here.

`fetched_at` is an optional API snapshot timestamp (or null).
`gal_curation.built_at` is the curation timestamp; `contacts_as_of` is the date
used to determine current contacts. These are separate from milestone dates.
Consumers choose their display timezone; readers preserve stored values.

Titles, status and journal codes retain source wording. Collision metadata
retains source strings (including numerical-looking strings and units).
`gal_publicationProvenance` describes identifier evidence, without implying a
linked page was checked. DOI, URL and citation values remain together in each
`gal_dois` entry. URLs are strings; validation does not test reachability.

## Validation and use

`CuratedRegistry.from_json(path)` validates before returning a reader whose
returned records are copies. `validate_registry(data)` performs the same checks
without transforming input. The builder validates candidates before atomically
replacing the output.

1. JSON Schema checks containers, nested types, required fields and date formats.
   Unknown optional fields are allowed. Maps such as identifier source counts
   still enforce their documented value types.
2. Python checks counts and uniqueness of native identifiers. Dangling links and
   contradictory milestone order are not structural errors.

The schema ships in both the wheel and source distribution:

```python
from importlib.resources import files

schema_text = (
    files("analysis_lister.registry")
    .joinpath("schemas/curated-v2.schema.json")
    .read_text(encoding="utf-8")
)
```

External validators must enable `date` and `date-time` format assertions. The
package uses `jsonschema` with `FormatChecker` and explicitly depends on
`rfc3339-validator`, so timestamp checks cannot silently disappear with optional
format dependencies. See the [validator documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/#validating-formats).

When evolving curation, update the schema and documentation, add a synthetic
fixture for the new feature, and run contract and regression tests. Upstream
mapping tests verify how API changes are adapted; frozen curated fixtures verify
what downstream readers can continue to consume.
