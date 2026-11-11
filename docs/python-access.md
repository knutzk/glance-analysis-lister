<!-- SPDX-FileCopyrightText: 2024-2026 Knut Zoch -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Use saved records in Python

Use the Python API when you want to inspect saved records or build your own
presentation from the package's selected collections. Reading and preparation
work offline: they do not download data or write pages. Use the CLI to retrieve
GLANCE data, build a registry or render the standard website output.

The first example reads stored records as they are. The second applies a group
policy and lifecycle rules to prepare the values used by the generated pages.
Run them from the repository root with the package installed; both use invented
data from the public demo.

## Read records

Load and validate a registry without importing downloaders, authentication
clients or renderers:

```python
from analysis_lister.registry import CuratedRegistry

registry = CuratedRegistry.from_json("examples/synthetic_registry.json")
for paper in registry.records("papers"):
    print(paper["referenceCode"])
```

For the synthetic registry, this prints:

```text
DEMO-2099-01
DEMO-2099-02
DEMO-2099-03
DEMO-2099-04
```

### Available imports

| Import path | Names | Purpose |
| --- | --- | --- |
| `analysis_lister.registry` | `CuratedRegistry`, `validate_registry`, `RESOURCES`, `SCHEMA` | Read and validate stored curated data. |
| `analysis_lister.views.profiles` | `GroupProfile`, `PublicationPolicy` | Describe a group's presentation and publication selection. |
| `analysis_lister.views.curation` | `load_publication_policy` | Read a policy from TOML. |
| `analysis_lister.views.prepare` | `prepare_group` | Produce collections without rendering or network access. |

`RESOURCES` is `("analyses", "papers", "confnotes", "pubnotes")`.
`SCHEMA` is `"glance-curated-registry"`.
`validate_registry(data)` validates a decoded JSON object without changing it,
returns `None` on success, and raises `ValueError` for invalid curated data.
Validation also logs a warning if generator metadata is absent or its code
fingerprint differs. That warning does not reject valid data or change the input.

### Reader reference

| Call or attribute | Result |
| --- | --- |
| `CuratedRegistry(data)` | Validate and own a deep copy of a decoded curated JSON object. |
| `CuratedRegistry.from_json(path)` | Read UTF-8 JSON from a string or path-like filename, then validate it. |
| `registry.metadata` | Deep-copied dictionary of all container fields except the four resource arrays. |
| `registry.records(resource)` | Tuple of deep-copied record dictionaries in snapshot order. |
| `registry.get(resource, reference)` | Deep-copied record with that native identifier, or `None` if absent. |
| `registry.resolve_link(link)` | Follow an explicit relationship, returning a deep-copied record or `None` for an absent target. |

Resources are the exact strings in `RESOURCES`; an unknown resource raises
`KeyError`. Link objects must have a nonempty `referenceCode` and a `type` of
`Analysis`, `Paper`, `CONF note` or `PUB note`; malformed or unsupported links
raise `ValueError`. A note link uses its native temporary identifier, not its
public final label. Validation allows dangling relationships; lookup does not
fetch missing targets or guess their identity.

Malformed JSON raises `json.JSONDecodeError` (a `ValueError` subclass), invalid
curated data raises `ValueError`, and filesystem errors propagate as `OSError`
subclasses. Match exception types, not exact message wording. Reading never
enriches records, applies group policies or makes network requests. See [stored values](file-reference.md#missing-values-people-and-dates)
for the
difference between missing, null and empty values.

## Prepare a group view

Preparation produces collections that can be used without Markdown rendering:

```python
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

policy = PublicationPolicy(groups=("DEMO",))
view = prepare_group(registry, GroupProfile("DEMO", publication_policy=policy))
for publication in view.archive:
    for link in publication.details.publication_records:
        print(publication.label, link.label, link.url)
```

The archive is ready for a custom publication display. Use `view.ongoing` for
analysis cards, or read the registry directly when you need stored fields rather
than selected display values. For a TOML policy, pass the result of
`load_publication_policy(path, "DEMO")` instead of constructing it in Python.

### Profiles and policy loading

| Call | Inputs and defaults |
| --- | --- |
| `PublicationPolicy(title="", groups=(), subgroups=(), keywords=())` | Optional title and OR-based selection criteria. Criteria accept lists or tuples of nonempty strings, trim whitespace, remove duplicates and are stored as tuples. |
| `GroupProfile(group, title="", publication_policy=None)` | Required nonempty group name; an empty display title falls back to that name. Accepts a `PublicationPolicy` or `None`. |
| `load_publication_policy(path, group)` | Read and validate every table in a TOML file; return the requested policy, or `None` when its group table is absent. Passing `None` as the path also returns `None`. |
| `prepare_group(registry, profile)` | Accept a `CuratedRegistry` and `GroupProfile`; return a prepared `GroupView` without I/O or renderer imports. |

Invalid profile or policy values raise `ValueError`. Loading a nonexistent policy
file raises `FileNotFoundError`; this differs from a missing group table in a
valid file. Malformed TOML raises `tomllib.TOMLDecodeError`, a `ValueError`
subclass. See [policy fields](selection.md#publication-policies) for file syntax.

`None` means the identifier-token fallback for publication selection;
`PublicationPolicy()` is an explicitly empty policy that selects no publications.
Neither changes ongoing-analysis membership. Python preparation does not print
the CLI's missing-policy warning. `prepare_group` raises `ValueError` if no
record has matching membership or curation evidence; an affiliated group can
still yield empty displayed collections because lifecycle rules exclude records.

### Read prepared collections

Prepared result objects use attributes, not dictionary indexing. Consume the
documented attributes below; their constructors, other attributes, rule traces
and renderer helpers are internal. Read additional record fields through
`CuratedRegistry` when you need the stored values rather than a display value.

| `GroupView` attribute | Meaning |
| --- | --- |
| `profile` | The `GroupProfile` supplied to preparation. |
| `ongoing` | Tuple of selected `AnalysisRow` objects, ordered by native reference. |
| `needs_review` | Tuple of analysis rows needing classification review, ordered by native reference. |
| `publications` | Tuple of selected `PublicationRow` objects, including records not ready for the archive. Do not depend on its order. |
| `archive` | Tuple of submitted/published papers and released notes, known dates newest first and undated entries last. Superseded notes remain present; the browser applies their visibility filter. |
| `source_metadata` | Copied registry container metadata. |

| Row | Supported attributes |
| --- | --- |
| Both row types | `reference` (native identifier), `title` (display title), `metadata` (search and record attributes). |
| `AnalysisRow` | `status` (recorded wording or a missing-value label), `stage` (derived review stage), `contacts`, `editors`, `board`, `board_chairs`, `keywords` (tuples of strings). |
| `PublicationRow` | `resource`, `label` (display identifier), `state` (derived lifecycle), `date` (display date string or `None`), `subgroups` (tuple of strings), `details` (typed detail object). |

Analysis and publication `metadata` dictionaries expose `text` (search text),
`subgroups`, `keywords`, `triggers` and `statistical_tools` (lists of strings),
and `leading_subgroup` (string or `None`). Extra keys can be added; they do not
imply a corresponding browser filter. Derived labels are display values, not
an exhaustive enumeration of future source statuses.

For publications, these `details` attributes support custom display code:

| Attribute | Type and meaning |
| --- | --- |
| `publication_records`, `links` | Tuples of link objects with `label: str` and `url: str \| None`. A missing URL is a readable label, not a link to follow. |
| `contacts`, `editors`, `board`, `board_chairs` | Tuples of recorded names. |
| `cite_as` | Tuple of plain-text citation lines for papers; empty for notes. Includes title, available references and aligned DOI entries. |
| `last_milestone` | `(label, date)` tuple, or `None`. |
| `cds_url` | CDS URL string, or `None`. |
| `conf_note`, `pub_note` | Note detail object for the corresponding resource, otherwise `None`. |

A note detail object exposes `people` (tuple of roles with `label` and `names`
tuple), `tags` (tuple of groups with `label` and `values` tuple), and `superseded`
(boolean). Use the stored note's `supersededBy` relationships to resolve targets.

Profiles and result objects prevent attribute reassignment, but nested lists
and dictionaries are mutable. Treat a prepared view as read-only; use
`copy.deepcopy(view)` before modifying nested data. Do not use `attrs.asdict(view)`
or pickle output as a durable interchange format: internal attributes are not
part of this API scope. Save the curated registry to prepare again with a
compatible package, and keep its API snapshot so the registry can be rebuilt
after an incompatible change.

`controls`, `decisions` and provenance dictionaries expose internal UI/rule
evidence for diagnostics. Their structure and reason strings are not part of
the supported Python interface. The [diagnostic report](problems.md#read-the-diagnostic-report) is the
human-facing explanation of those decisions.

## Use the documented interface

The imports and result attributes above define the current Python integration
scope. Pin the package version in a consuming application and follow the
[upgrade guide](upgrading.md) before replacing it. Internal helpers and constructors
are not public APIs; use the CLI for file-writing workflows. The reader methods
provide access to stored records, but do not make every key in those dictionaries
a stable Python attribute or an external JSON contract. Stored fields can change
and registries may need rebuilding after an upgrade; the documented reader
methods and prepared-result attributes are a separate interface.
