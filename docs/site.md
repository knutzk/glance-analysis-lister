# Local documentation site

[Documentation index](README.md)

The Zensical site displays the repository README and guides. Edit these source
files to update the site. The **Demo** section contains all four generated pages;
the ongoing-analysis and publication guides also embed individual records.

## Preview

From the repository root, create a Python 3.13 environment if needed, then start
the server:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-docs.txt
python scripts/docs.py serve
```

Open <http://127.0.0.1:8000/glance-analysis-lister/>. The preview reloads when you
save a source file. Stop it with **Ctrl+C**. For another port, use
`python scripts/docs.py serve --dev-addr 127.0.0.1:8001`.

The documentation requirements install the package in editable mode and the
pinned Zensical version. If you installed them before the live examples were
added, rerun the install command above. Use the same environment to install and
serve; in a new terminal, activate `.venv` again or run
`.venv/bin/python scripts/docs.py serve` directly. A missing `jsonschema` module
means the current environment lacks a package dependency.

Example rendering runs offline without CERN credentials. The light/dark switch
beside search starts with your system preference and remembers manual changes.
On wide screens, page navigation appears on the left and the current page’s
headings appear in a separate table of contents on the right.

If an ignored `ROADMAP.md` exists in the repository root, the preview adds it to
navigation automatically. It uses an ignored `.zensical-preview.yml` generated
from `zensical.toml`; no tracked configuration changes are needed. Restart the
preview after adding or removing the roadmap. Static builds exclude it.

## Preview your group alongside Demo

From this repository root, activate the documentation environment described
above. To display TOPQ pages from an existing curated registry:

```bash
analysis-lister render-group --group TOPQ \
  --snapshot glance_curated_registry.json --output-dir pages/topq
python scripts/docs.py serve --group-pages TOPQ=pages/topq
```

Open <http://127.0.0.1:8000/glance-analysis-lister/>. **TOPQ (local data)** appears
beside **Demo**, with ongoing analyses, papers, conference notes and public notes.
The synthetic demo remains available. The group pages use the site's existing
search, filtering, navigation and assets; no landing-page or asset copies are
needed. Stop the preview with **Ctrl+C**.

If you need fresh CERN data, replace the rendering command above with:

```bash
analysis-lister refresh --groups TOPQ --output-dir pages/topq --login
```

Omit `--login` when reusing stored credentials. A single group writes directly
to the requested output directory; the default curated snapshot is
`glance_curated_registry.json` in the calling directory. If it lives elsewhere,
pass its actual path to `render-group --snapshot`. These commands use the bundled
TOPQ publication policy; pass `--curation-config PATH` to use your own.

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

## Build static HTML

```bash
python scripts/docs.py build
```

This validates links and anchors and writes HTML to `site/`. Run only one build
or preview at a time: both commands clear the generated `site-src/` and `site/`
directories when they start. Edit the original sources, not those copies.
Group previews use their separate cache directories but still share the generated
preview configuration; run only one documentation command at a time.

## Inspect a CI build

The CI workflow builds the public documentation on pull requests, pushes and
manual runs. Its `documentation` job uses the same strict build command and
uploads `documentation-site`, retained for 14 days. The browser job separately
checks the synthetic demo and policy tutorial.

In the repository's **Actions** tab, open the relevant CI run and download
`documentation-site` from its artifacts. Extract its contents into
`preview/glance-analysis-lister/`, so that `index.html` is directly inside that
directory. Serve it with:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory preview
```

Open <http://127.0.0.1:8000/glance-analysis-lister/> and stop with **Ctrl+C**.
This preserves the repository subpath used by the configured site URL. The
artifact includes the synthetic demo; it excludes the local roadmap and demo
diagnostic reports. Uploading the artifact does not deploy a public site.

## Add or configure content

The root [`zensical.toml`](../zensical.toml) defines navigation, colours and styles
for the package documentation site. The standalone demo has its own configuration,
landing page and policy under [`examples/demo/`](../examples/demo/index.md); its
[`zensical.toml`](../examples/demo/zensical.toml) is a template copied to
`examples/demo/work/zensical.toml` during setup. That local copy reads
`examples/demo/work/pages/` and builds `examples/demo/work/site/`.
The [CERN data walkthrough](cern-demo.md) adds
CERN pages alongside Demo in the standalone site, using this same local copy.
Both sites share `requirements-docs.txt` and `docs/stylesheets/site.css`.
[`scripts/docs.py`](../scripts/docs.py) lists the public inputs copied into
`site-src/`. Add a new guide to both the input list and navigation, then restart
the preview. The explicit list excludes private snapshots, generated analysis
pages and reports elsewhere in the checkout.

The `BEGIN LIVE` / `END LIVE` blocks in the view guides contain screenshot
fallbacks for GitHub. During staging, the script replaces them with HTML from
the package's renderer and copies its shared CSS and JavaScript. Only
`examples/synthetic_registry.json` supplies records. The preview updates when
that fixture changes; restart it after editing renderer code.
Site styles hide the filter controls and result counts in these single-record
examples; titles still expand the details.

The full demo uses the same fixture and `examples/demo/publication-curation.toml`
as the [standalone tutorial](../examples/README.md). It retains all search, sort
and filter controls. The builder renders in a temporary directory and copies only
the four Markdown pages into the site, alongside the maintained demo overview.
Diagnostic reports are not included. Changes to the tracked fixture or policy
regenerate both the full demo and the embedded examples during preview.

Release notes are staged from the explicitly listed `.github/release-notes/`
files as Markdown pages under `docs/release-notes/`. Edit the original `.txt`
files; the site adds a version heading and historical-context notice. Preview
reloads those edits, and the source archive includes the originals. See
[release qualification](releases.md#release-notes) when adding another version.

The configured URL uses the expected GitHub Pages repository subpath. The site
is local development documentation; no deployment workflow is configured.
For other settings, see the [Zensical configuration guide](https://zensical.org/docs/setup/basics/).
