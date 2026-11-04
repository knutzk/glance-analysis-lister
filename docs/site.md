# Local documentation site

[Documentation index](README.md)

The Zensical site displays the repository README, guides and roadmap. Edit these
source files to update the site.

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

The documentation requirements install the pinned Zensical version. The
light/dark switch beside search starts with your system preference and remembers
manual changes.
Page headings appear within the left navigation, leaving more room for content.

## Build static HTML

```bash
python scripts/docs.py build
```

This validates links and anchors and writes HTML to `site/`. Run only one build
or preview at a time: both commands clear the generated `site-src/` and `site/`
directories when they start. Edit the original sources, not those copies.

## Add or configure content

[`zensical.toml`](../zensical.toml) defines navigation, colours and styles.
[`scripts/docs.py`](../scripts/docs.py) lists the public inputs copied into
`site-src/`. Add a new guide to both the input list and navigation, then restart
the preview. The explicit list excludes private snapshots, generated analysis
pages and reports elsewhere in the checkout.

The configured URL uses the expected GitHub Pages repository subpath. The site
is local development documentation; no deployment workflow is configured.
For other settings, see the [Zensical configuration guide](https://zensical.org/docs/setup/basics/).
