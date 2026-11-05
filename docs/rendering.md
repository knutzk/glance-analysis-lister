# Rendering and policies

[Documentation index](README.md)

Render a group from a saved curated registry:

```bash
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json \
  --output-dir docs/analyses
```

The command writes `ongoing.md`, `papers.md`, `confnotes.md`, `pubnotes.md`,
`view-report.json` and shared browser assets. Without `--output-dir`, it writes to
`pages/group`. Rendering is offline. See [provenance](provenance.md) for output
fingerprints, reproducibility and unchanged-file handling.

## Generated file and URL contract

The supported output names are:

| Output | Purpose |
| --- | --- |
| `ongoing.md` | Ongoing-analysis cards. |
| `papers.md`, `confnotes.md`, `pubnotes.md` | Separate publication tables. |
| `assets/gal-common.css`, `assets/gal-common.js` | Shared presentation and controls. |
| `assets/gal-ongoing.css`, `assets/gal-ongoing.js` | Analysis-card presentation and controls. |
| `assets/gal-papers.css`, `assets/gal-papers.js` | Paper-table presentation and controls. |
| `assets/gal-notes.css`, `assets/gal-notes.js` | CONF/PUB-note presentation and controls. |
| `view-report.json` | Private [diagnostic report](diagnostics.md). |

New files may be added. Existing names and the URL forms below are compatibility
surfaces; changes must follow the [compatibility policy](compatibility.md).
Generate and install pages and assets together. HTML layout, CSS class names,
internal element IDs and JavaScript functions are not extension APIs.

The consuming site owns the origin, group-directory prefix and conversion of
Markdown paths to URLs. For example, Zensical normally serves `papers.md` at
`papers/`. Moving the site or changing its URL style requires redirects in that
site; the renderer does not manage them.

### Record fragments

The record's group and native identifier determine its fragment. Titles,
publication display labels and row order do not. For the DEMO fixture:

| Page | Fragment |
| --- | --- |
| Ongoing | `#analysis-demo-ana-demo-2099-01` |
| Papers | `#publication-papers-demo-demo-2099-01` |
| CONF notes | `#confnote-demo-conf-demo-2099-01` |
| PUB notes | `#pubnote-demo-pub-demo-2099-01` |

These emitted record fragments are supported. The current form combines the
page-specific prefix with the group and native reference in lowercase, replacing
runs outside `a-z`, `0-9` and `-` with `-` and trimming edge hyphens from that
combined group/reference part. Prefer copying an emitted fragment to constructing
one. IDs for controls, headings and detail panels are internal.

The fragment stays the same while the group and native identifier stay the same
and the record remains on that page. A source change, lifecycle transition or
policy edit can remove the record from the page; there is no historical-record
redirect. An ongoing-card permalink reveals and expands its card even when
filters would hide it. Publication fragments identify rows but do not override
filters or expand details; include the appropriate filters when sharing them.

### Filter parameters

Use normal URL encoding for values, including spaces and commas. Repeat a
parameter to select several values where the table permits it; do not split a
subgroup name at commas.

| Pages | Parameter | Values and default |
| --- | --- | --- |
| All four | `q` | Case-insensitive substring search; omitted means no search restriction. |
| Ongoing | `subgroup` | Exact subgroup name, repeated for OR selection. Omitted means all subgroups. |
| Ongoing | `sort` | `stage-desc` (default), `stage-asc`, or `reference`. |
| Papers and notes | `after`, `before` | Inclusive `YYYY-MM` bounds. Omitted means no bound. Undated rows satisfy After but not Before. |
| Papers | `status` | `published` or `under-review`, repeated for OR selection. Omitted means both. These mean DOI present or absent. |
| Notes | `supersession` | `non-superseded` (default), `superseded`, or `all`. |

Controls restore these values when opening or reloading a link and on browser
history navigation. Filters from different categories combine with AND. A link
preserves selection intent, not a fixed set of results: the snapshot and policy
still determine the available records and subgroup choices.

Controls may normalise a URL by trimming search text, removing empty/default
values, or reordering parameters. Unknown filter values are not part of this
contract. Other application parameters and the fragment survive updates and
Reset. The names in this table are reserved for the package; `subgroup` on note
pages is a retired control and is removed when the URL is normalised.

See [ongoing links](ongoing.md#share-a-filtered-view) and
[publication links](publications.md#share-a-filtered-view) for examples.

## Publication policies

The bundled [`publication-curation.toml`](../publication-curation.toml) controls
publication inclusion. It is used regardless of the working directory. Edit it
to maintain shared policies, or pass `--curation-config PATH` for an alternative.
Each group has its own table:

```toml
[groups.TOPQ]
title = "Top Quark Physics"
groups = ["TOPQ"]
subgroups = []
keywords = []
```

Only a top-level `groups` table is accepted. Each `[groups.NAME]` table accepts
these fields; unknown fields or invalid types fail validation, including in
tables for other groups.

| Field | Type / default when omitted | Meaning |
| --- | --- | --- |
| `title` | Nonempty string / group display title | Publication-page title. |
| `groups` | List of nonempty strings / `[]` | Match an internal identifier's group token (case-insensitive), or an exact leading/additional main-group affiliation. |
| `subgroups` | List of nonempty strings / `[]` | Match an exact leading/additional subgroup name. A name containing a comma remains one string. |
| `keywords` | List of nonempty strings / `[]` | Match an exact label after trimming whitespace and ignoring case. |

Criteria are combined with **OR**: any match includes the publication. These
rules select publications independently of ongoing-analysis membership.

Missing publication affiliations or metadata can be supplied by an explicitly
linked analysis; the report records that derivation. No extra group criterion
is added implicitly. An explicitly empty policy selects no publications.

If a group's table is missing, the command warns on stderr and falls back to
its internal identifier's group token. Define a table even for a group that
selects only its own publications. `title` sets publication-page headings;
`--group-title` sets the ongoing-page heading and supplies the fallback when
the policy omits `title`; without either, headings use the group name. Policy
strings are trimmed, and duplicate criteria are removed when loading.

## Enable browser assets

For output under `docs/analyses`, add these entries to the consuming site's
configuration. Load the common files before the view-specific files:

```yaml
extra_css:
  - analyses/assets/gal-common.css
  - analyses/assets/gal-ongoing.css
  - analyses/assets/gal-papers.css
  - analyses/assets/gal-notes.css
extra_javascript:
  - analyses/assets/gal-common.js
  - analyses/assets/gal-ongoing.js
  - analyses/assets/gal-papers.js
  - analyses/assets/gal-notes.js
```

One asset copy can serve all groups. The controls support Zensical instant
navigation, keyboard operation and dynamically inserted content. Without
JavaScript, all records and details remain readable. Filtering makes no live
requests.

## Read the output

The guides to [ongoing analyses](ongoing.md) and [publication tables](publications.md)
explain the generated views with synthetic examples. Use the
[diagnostic report](diagnostics.md) to understand uncertain states and missing
or conflicting relationships.
