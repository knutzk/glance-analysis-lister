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
Page headings appear within the left navigation, leaving more room for content.

If an ignored `ROADMAP.md` exists in the repository root, the preview adds it to
navigation automatically. It uses an ignored `.zensical-preview.yml` generated
from `zensical.toml`; no tracked configuration changes are needed. Restart the
preview after adding or removing the roadmap. Static builds exclude it.

## Build static HTML

```bash
python scripts/docs.py build
```

This validates links and anchors and writes HTML to `site/`. Run only one build
or preview at a time: both commands clear the generated `site-src/` and `site/`
directories when they start. Edit the original sources, not those copies.

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

[`zensical.toml`](../zensical.toml) defines navigation, colours and styles.
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
