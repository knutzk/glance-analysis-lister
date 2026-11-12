# Building and maintaining a group website

[Documentation overview](README.md)

The package generates Markdown and browser assets; your website builder turns
those files into a site. This separation lets you keep the same data workflow
while choosing where the pages appear, how groups are organised and who can
read them. The standalone demonstrator already supplies the website setup.

For an existing group website, generate into a staging directory, inspect the
result, then copy only the intended pages and assets into the site source.
The diagnostic report is for your review and may contain private record details;
it should remain outside the website's published content.

[CERN demonstrator](cern-demo.md) · [Selection policies](selection.md) · [Output contract](file-reference.md)

## What generation produces

Each render writes `ongoing.md`, `papers.md`, `confnotes.md`, `pubnotes.md`, shared
CSS/JavaScript assets and `view-report.json`. It uses one group and a saved curated
registry, without network access. Choose an explicit output directory; the
standalone `render-group` default is `pages/group`.

Deploy pages and assets from the same generation together. The site's navigation
and Markdown-to-URL conversion are configured in the consuming website.

## Reuse a snapshot offline

If you already have a curated registry, render it directly. For example, from
this checkout, use the public fixture and its policy:

```bash
grove render-group --group DEMO \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/publication-curation.toml \
  --output-dir examples/demo/work/pages
```

This produces four ongoing analyses and twelve archived publications, with no
diagnostic warnings. Each note page initially hides one superseded note. Use the
[demo tutorial](../examples/README.md#tutorial-change-publication-selection) to
edit a policy copy and see which pages change.

For your own data, replace the snapshot, group and policy paths. `render-group`
handles one group per invocation; use separate output directories when rendering
several groups from the same snapshot. The group selects ongoing analyses by
their leading or additional main-group affiliation and identifies the policy
table used for publications. A publication policy can select other groups,
subgroups or keywords; it does not change ongoing-analysis membership.
Browser filters only narrow records already included in a generated page.

If curation rules or citation data changed, first rebuild from the saved API
snapshot, then render the new registry:

```bash
grove build-registry --api-snapshot data/api.json \
  --doi-cache data/doi-metadata.json --output data/curated.json
grove render-group --group TOPQ --snapshot data/curated.json \
  --curation-config publication-curation.toml --output-dir pages/topq
```

These paths assume you have saved the API snapshot and chosen your own policy
and [citation store](citations.md#choose-a-store). Run the commands in order and
continue only if the build succeeds. The synthetic fixture is already curated;
it is a rendering input, not an API input to `build-registry`.

## Preview your group alongside Demo

From the repository root, install `requirements-docs.txt` in your active
environment. TOPQ is an example: substitute your group and directory consistently.
To display TOPQ pages from an existing curated registry:

```bash
grove render-group --group TOPQ \
  --snapshot glance_curated_registry.json --output-dir pages/topq
python scripts/docs.py serve --group-pages TOPQ=pages/topq
```

Open <http://127.0.0.1:8000/glance-grove/>. **TOPQ (local data)** appears
beside **Demo**, with ongoing analyses, papers, conference notes and public notes.
The synthetic demo remains available. The group pages use the site's existing
search, filtering, navigation and assets; no landing-page or asset copies are
needed. Stop the preview with **Ctrl+C**.

Use `--curation-config PATH` when rendering with your own publication policy.
For fresh source data, follow the [CERN walkthrough](cern-demo.md).

The preview reads already-rendered files. After regenerating them in another
terminal, it reloads their changes. It does not download or render real data
itself. To include more groups, repeat the option, for example
`--group-pages TOPQ=pages/topq --group-pages HIGP=pages/higp`, after rendering
each group into its own directory. Restart the server when changing the selection.

Group previews bind only to loopback and keep their generated sources and HTML
under the ignored `.cache/docs-group-preview/` directory. Only the four group
Markdown files are copied: snapshots, diagnostic reports and other files in the
render directory are excluded. The pages themselves contain your selected data;
keep `pages/` and the preview cache private. Ordinary previews omit these sections,
and public `build` commands reject `--group-pages` and use the public allowlist.

## Integrate into a consuming site

Render into a staging directory outside the site's `docs_dir`. Inspect its
[diagnostic report](problems.md#read-the-diagnostic-report), then copy the four Markdown pages and assets
into the site source. A site builder can publish JSON files even when no page
links to them; keeping `view-report.json` outside `docs_dir` avoids including it
in the built site. The pages themselves still contain the selected records and
must be appropriate for the site's audience.

For example, from the consuming repository with the package installed, a saved
curated snapshot at `data/curated.json`, and your policy at
`publication-curation.toml`:

```bash
grove render-group --group TOPQ --snapshot data/curated.json \
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
superseded notes. The [browser checks](contributing.md#browser-and-site-checks)
cover these behaviours in the default Zensical theme.

## Refresh group pages in one command

From the repository that consumes the pages, run:

```bash
grove refresh --groups TOPQ --output-dir docs/analyses --login
```

Refresh downloads one API snapshot, builds the curated registry offline, then
renders the group pages. The stare client manages browser single sign-on (SSO),
credential storage and token refresh. Omit `--login` to reuse stored credentials.
Refresh does not download HTML or query citation services.

For several groups:

```bash
grove refresh --groups TOPQ HIGP --output-dir pages
```

A single group writes directly into the output directory. Multiple groups use
lowercase subdirectories, such as `pages/topq/` and `pages/higp/`. Group tokens
must be uppercase and unique.

Configuration and destination collisions are checked before authentication.
Stages run sequentially and stop at the first failure; completed outputs remain.
There is no rollback across the whole refresh or all rendered pages. The final
summary lists snapshot paths, group outputs, diagnostic reports, counts and
elapsed time. See [recovery](problems.md#validation-and-recovery) to resume a failed run.

## Check an update before publishing

Inspect the generated report, then preview all four pages in the consuming site.
Check search, filters and expansion, including navigation between pages and any
repository URL prefix. Keep real pages on a site suitable for their audience.
The renderer does not publish the site or manage access permissions.

A render replaces files individually, so a failed write can leave mixed output.
Refresh stops at the first failing stage and keeps completed stages. Resume from
the failed step after correcting its cause; do not publish a partial result.

[Read the pages](pages.md) · [Warnings and recovery](problems.md) · [Reproducible output](data.md#reproducible-output)
