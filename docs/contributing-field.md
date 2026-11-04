# Trace a field from source to page

This walkthrough follows the existing trigger field through curation, prepared
views and an analysis card. It gives you a working example of the layers to
change when adopting another field. Everything runs offline with invented data.
Start from a checkout with the [development environment](development.md#set-up-and-run-checks)
installed, and run commands from the repository root.

## Create a small API example

Use the shared synthetic test fixture, which supplies one record per resource,
and configure its analysis for this exercise. API validation requires nonempty
resource collections. This writes only under the ignored
`pages/field-walkthrough/` directory:

```bash
python - <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, "tests")
from view_fixtures import api_fixture

api = api_fixture()
for resource in ("papers", "confnotes", "pubnotes"):
    api[resource][0]["status"] = "Phase 1 Active"
record = api["analyses"][0]
record.update(
    shortTitle="Synthetic field walkthrough",
    status="Phase 0 Active",
    groups={"leadingGroup": {"name": "DEMO"}},
    relatedPublications=[],
)
record["metadata"]["triggers"] = [{"name": "Invented trigger"}]
output = Path("pages/field-walkthrough/api.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
print(output)
PY

analysis-lister build-registry \
  --api-snapshot pages/field-walkthrough/api.json \
  --output pages/field-walkthrough/curated.json
```

The API fragment `"triggers": [{"name": "Invented trigger"}]` becomes
`"gal_triggers": ["Invented trigger"]` under `metadata`. The original `triggers`
key is removed during field selection. Confirm the stored value and the prepared
view separately from rendering:

```bash
python - <<'PY'
from analysis_lister.registry import CuratedRegistry
from analysis_lister.views.prepare import prepare_group
from analysis_lister.views.profiles import GroupProfile, PublicationPolicy

registry = CuratedRegistry.from_json("pages/field-walkthrough/curated.json")
record = registry.get("analyses", "ANA-DEMO-2099-01")
assert record["metadata"]["gal_triggers"] == ["Invented trigger"]
assert "triggers" not in record["metadata"]
view = prepare_group(
    registry, GroupProfile("DEMO", publication_policy=PublicationPolicy(groups=("DEMO",)))
)
assert len(view.ongoing) == 1
assert view.ongoing[0].metadata["triggers"] == ["Invented trigger"]
assert "Invented trigger" in view.ongoing[0].metadata["text"]
print("Stored field and prepared search metadata verified.")
PY
```

## Render and inspect it

```bash
analysis-lister render-group --group DEMO \
  --snapshot pages/field-walkthrough/curated.json \
  --curation-config examples/demo/publication-curation.toml \
  --output-dir pages/field-walkthrough/site
```

The result has one ongoing analysis; the unreleased publication records remain
in the registry but do not appear on publication pages. In `ongoing.md`, the
expanded card contains **Triggers** and **Invented trigger**, and its search
metadata contains the same value. For a browser preview, save this as
`pages/field-walkthrough/zensical.toml` (paths are relative to that file):

```toml
[project]
site_name = "Synthetic field walkthrough"
docs_dir = "site"
site_dir = "html"
nav = [{ "Ongoing analyses" = "ongoing.md" }]
extra_css = ["assets/gal-common.css", "assets/gal-ongoing.css"]
extra_javascript = ["assets/gal-common.js", "assets/gal-ongoing.js"]
```

```bash
python -m pip install -r requirements-docs.txt
python -m zensical serve -f pages/field-walkthrough/zensical.toml --dev-addr 127.0.0.1:8002
```

Open <http://127.0.0.1:8002/ongoing/> and expand the card. Searching for
`Invented trigger` keeps it; an unmatched term hides it. Stop the preview with
**Ctrl+C**. The full [synthetic demo](../examples/README.md) has examples and assets
for all four page types.

## Locate each responsibility

Paths below are relative to `analysis_lister/`.

| Layer | Trigger example | Responsibility when adopting a field |
| --- | --- | --- |
| Enrichment | `registry/enrichment.py`: `STRING_LIST_FIELDS` and `compact()` | Transform source representation only when needed. This mapping extracts names, trims them and removes duplicates in source order. |
| Retention | `registry/fields.py`: `METADATA` | Explicitly adopt the persisted field for the intended resources; enrichment alone does not retain it. |
| Schema | `registry/schemas/curated-v2.schema.json`: `metadata` and `noteMetadata` | Describe stored types and optionality. Here `gal_triggers` is an optional string list or null. |
| Prepared data | `views/models.py`: `RecordMetadata`; `views/analyses.py` | Expose the value and add it to search text without depending on a renderer. |
| Publication preparation | `views/publications.py`: `publication_filter_values()` | Decide whether an explicitly linked analysis can supply missing metadata; retain derivation evidence. |
| Rendering | `views/markdown/ongoing.py`, `papers.py`, `notes.py` | Render prepared values with escaping and readable no-JavaScript output. |

For a new field, first document its meaning, source shape and supported resources.
Decide how missing, null and empty values behave before adding it to retention
and the schema. An optional addition may fit v2; a change of meaning or a required
field needs the [compatibility review](curated-format.md#compatibility-policy).
Accepting null in stored curated data does not imply that every upstream shape
can be transformed: this example's source `triggers` must be a list.

Keep view-specific defaults in preparation. Do not enrich records during
registry reads, infer relationships, or add a dropdown just because metadata is
available. Ongoing triggers are searchable and visible in details without their
own filter control.

## Choose focused regressions

| Behaviour changed | Relevant tests and expected evidence |
| --- | --- |
| Source conversion or retention | `test_curated_registry.py`, `test_registry_fields.py`: transformed value survives, unused source keys disappear, inputs remain unchanged. |
| Stored contract | `test_registry_contract.py`: accepted and rejected shapes, sparse input, missing/null/empty distinctions. Add fixtures for new features; leave frozen fixtures unchanged. |
| Preparation or inheritance | `test_view_contracts.py`, `test_view_preparation.py`: values are available without rendering, explicit relationships control inheritance, diagnostics retain evidence. |
| Source-field access | `test_retained_field_contract.py`: all source paths consumed by preparation or rendering are retained, including conditional and sparse cases. |
| Display or search | `test_ongoing_rendering.py` and the corresponding publication tests: visible text, escaping and search metadata agree. |

For example, run the field-retention checks with
`python -m unittest discover -s tests -p 'test_registry_fields.py' -v`.
Before submitting, run the [standard checks](development.md#set-up-and-run-checks).
Changes to controls, JavaScript or site integration also need the relevant
[browser checks](development.md#browser-and-site-checks). A useful contribution
states what the field means, why it belongs in the contract, and which checks
demonstrate its stored, prepared and rendered behaviour.
