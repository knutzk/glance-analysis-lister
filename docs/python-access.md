# Python access

[Documentation index](README.md)

These examples use current interfaces. The supported Python API and its v1.0
compatibility guarantees are not yet finalized.

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
```

`get(resource, reference)` looks up a native identifier. `resolve_link(link)`
follows an explicit relationship. Returned records and metadata are copies;
reading does not enrich them or make network requests. See the
[curated contract](curated-format.md) for validation and identity rules.

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

Prepared rows expose `metadata` with search text and record attributes such as
keywords, triggers and subgroups. `view.controls` describes the available UI
choices: ongoing subgroups and sorting, paper publication status, and note
supersession. Having a metadata field does not imply that the UI has a filter
for it. The [diagnostic report](diagnostics.md) records controls
and derivation evidence.

`load_publication_policy(path, group)` in `views.curation` reads the same TOML as
the CLI. It returns `None` for missing configuration; `PublicationPolicy()` is
an explicitly empty policy. See [publication policies](rendering.md#publication-policies)
for their selection rules.
