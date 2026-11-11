# Maintaining the documentation

[Documentation index](README.md)

The Zensical site displays the repository README and guides. Edit these source
files to update the site. The **Demo** section contains all four generated pages;
the page-exploration guide also embeds individual records.

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

The `BEGIN LIVE` / `END LIVE` blocks in the page-exploration guide contain screenshot
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

The [public development site](https://knutzoch.org/glance-analysis-lister/) uses
the repository subpath. The Publish documentation workflow runs the same
strict build on pushes to `main` and publishes `site/` to GitHub Pages.
For other settings, see the [Zensical configuration guide](https://zensical.org/docs/setup/basics/).

## Regenerate screenshots

The four PNG screenshots are browser captures of the Zensical views built from [`examples/synthetic_registry.json`](../examples/synthetic_registry.json).
They use an explicit DEMO publication policy and only independently invented
data.

From the repository root, with Python 3.13, Chrome and a compatible ChromeDriver:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -r tests/browser/requirements.txt
python scripts/capture_screenshots.py --driver /path/to/chromedriver
```

Set `CHROME_BINARY` to select a different Chrome executable. For environment
setup, see [development and validation](development.md).

The script builds a strict temporary site and runs the Zensical browser checks
at a 1440-pixel browser width. The gallery pair starts at the search controls,
leaving out the page heading, curation explanation and provenance footer.
It shows all four analysis cards collapsed and one paper expanded. Both images
use the same width and height, with a small margin for shadows; the shorter
collection gets empty space below its records so nothing is stretched or cut off.
Browser and font differences can change the exact dimensions and pixels.

The script also expands the original analysis example for its separate detail
capture and extends the viewport as needed. It replaces four PNGs: the matched
`ongoing.png` and `papers.png` gallery views,
and the focused `ongoing-card.png` and `publication-row.png` fallbacks shown when
reading the guides on GitHub. The documentation site replaces those fallbacks
with live rendered examples. Temporary pages and reports are removed. Inspect
the images before committing them. The fixtures and capture script are
GPL-3.0-only; the site uses Zensical's built-in theme.

## Command diagram

[`command-flow.svg`](images/command-flow.svg) is a hand-maintained vector diagram used
in the [command workflow guide](data.md#how-the-commands-connect). Edit the SVG directly; it is not produced by the screenshot
script. Keep snapshots visually distinct from commands, center the `refresh`
caption, and preserve equal gaps within the command row and matching gaps between
the source, refresh frame, output and preview. Keep the output-to-preview turn.
Inspect the rendered workflow guide at desktop width with both navigation columns, in
light and dark mode, after changing it. Command names use monospace type; step
numbers sit above them so the saved-file handoffs remain legible. The image links
to its full-size SVG for small screens.

## Citation diagram

[`citation-flow.svg`](images/citation-flow.svg) is the maintained source for the
[citation-flow figure](citations.md#how-citations-reach-the-pages). Edit the SVG
directly. Keep saved data distinct from build/render steps and show citation-store
maintenance separately. The figure must retain the rebuild-then-render handoff
after store edits and the DOI fallback when citation text is missing.

Check the embedded figure in light and dark mode, including a manual site-theme
override, and at desktop and mobile widths. Its image link opens the SVG at full
size. New public figures need entries in both `scripts/docs.py`'s explicit staging
list and `MANIFEST.in` so site builds and source archives include them.

## Data-flow diagram

[`data-flow.svg`](images/data-flow.svg) illustrates
[how GLANCE data becomes a website](data.md#from-glance-to-a-website). Edit the SVG
directly, keeping saved files distinct from in-memory views. Preserve the network
boundary, the enrichment and group-configuration inputs, and the separation
between rendered files and the consuming website. Check the embedded figure in
both themes and at desktop and mobile widths, as for the citation diagram.

## Selection diagram

[`selection-flow.svg`](images/selection-flow.svg) illustrates the
[three selection decisions](selection.md#three-decisions). Keep analysis membership
separate from publication policy, and retain the review cross-connection through
explicit analysis links. Distinguish lifecycle placement from browser filtering.
Use consistent numbered headings, with path names outside the first boxes. Check
both themes, desktop/mobile layouts and the full-size link after editing the SVG.
