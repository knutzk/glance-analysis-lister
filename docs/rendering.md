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
| `view-report.json` | Private diagnostic report with a [supported summary](diagnostics.md#supported-report-summary). |

New files may be added. Existing names and the URL forms below are compatibility
surfaces; changes must follow the [change policy](compatibility.md#change-and-deprecation-policy).
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

For pages and assets under `docs/analyses`, add these entries to the existing
`[project]` table in the consuming site's `zensical.toml`. Merge with any existing
asset lists, keeping common files before view-specific files:

```toml
extra_css = [
  "analyses/assets/gal-common.css",
  "analyses/assets/gal-ongoing.css",
  "analyses/assets/gal-papers.css",
  "analyses/assets/gal-notes.css",
]
extra_javascript = [
  "analyses/assets/gal-common.js",
  "analyses/assets/gal-ongoing.js",
  "analyses/assets/gal-papers.js",
  "analyses/assets/gal-notes.js",
]
```

One asset copy can serve all groups. The controls support Zensical instant
navigation, keyboard operation and dynamically inserted content. Without
JavaScript, all records and details remain readable. Filtering makes no live
requests.

Use Tab or Shift+Tab to move between controls and Enter/Space to activate them.
The Collapse button returns focus to the record heading. On narrow screens,
Tab to an archive table's named scroll region and use the arrow keys to reach
columns outside the viewport; its inset outline marks keyboard focus. Without
JavaScript, filters are hidden and details are already open, including those of
superseded notes. The [browser checks](development.md#browser-and-site-checks)
cover these behaviours in the default Zensical theme.

## Integrate into a consuming site

Render into a staging directory outside the site's `docs_dir`. Inspect its
[diagnostic report](diagnostics.md), then copy the four Markdown pages and assets
into the site source. A site builder can publish JSON files even when no page
links to them; keeping `view-report.json` outside `docs_dir` avoids including it
in the built site. The pages themselves still contain the selected records and
must be appropriate for the site's audience.

For example, from the consuming repository with the package installed, a saved
curated snapshot at `data/curated.json`, and your policy at
`publication-curation.toml`:

```bash
analysis-lister render-group --group TOPQ --snapshot data/curated.json \
  --curation-config publication-curation.toml --output-dir generated/topq
```

After a successful render and report review, stage the intended site inputs:

```bash
mkdir -p docs/analyses/assets
cp generated/topq/ongoing.md generated/topq/papers.md \
  generated/topq/confnotes.md generated/topq/pubnotes.md docs/analyses/
cp generated/topq/assets/gal-*.css generated/topq/assets/gal-*.js docs/analyses/assets/
```

Keep `data/` and `generated/` out of version control when they hold private data.
Use a destination reserved for these pages; remove any reports or snapshots
previously placed there before building. Copying this selection does not clean
existing site inputs or make the update atomic.

Enable the assets as above. In the same `[project]` table, set `docs_dir = "docs"`
if it differs, and add a group entry to the existing `nav` list:

```toml
nav = [
  { "Analyses" = [
    { "Ongoing analyses" = "analyses/ongoing.md" },
    { "Papers" = "analyses/papers.md" },
    { "Conference notes" = "analyses/confnotes.md" },
    { "Public notes" = "analyses/pubnotes.md" },
  ] },
]
```

Preserve the site's other navigation entries. If you enable
`navigation.instant` in `[project.theme].features`, also set `[project].site_url`
to the site's full URL, including any repository subpath; the feature needs that
URL to recognise internal navigation. For a local-only site at the origin used
below, this is `site_url = "http://127.0.0.1:8001/"`.

With Zensical installed in the same environment, build or preview from that
repository:

```bash
python -m zensical build --clean --strict
python -m zensical serve --dev-addr 127.0.0.1:8001
```

Visit <http://127.0.0.1:8001/> using the site's configured URL prefix, if any.
Check all four pages, filtering and row expansion, including navigation between
pages when instant navigation is enabled. Stop the preview with **Ctrl+C**.
The [standalone demo](../examples/README.md) provides a complete configuration,
including the shared theme stylesheet and light/dark mode, for trying this with
synthetic data first.

## Read the output

The guides to [ongoing analyses](ongoing.md) and [publication tables](publications.md)
explain the generated views with synthetic examples. Use the
[diagnostic report](diagnostics.md) to understand uncertain states and missing
or conflicting relationships.
