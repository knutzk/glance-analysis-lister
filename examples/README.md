# Synthetic example

Run a complete local site without CERN access, or explore the same records in
the documentation site's **Demo** section. The [demo overview](demo/index.md)
suggests an interaction to try on each page.

[`synthetic_registry.json`](synthetic_registry.json) contains independently
invented DEMO-2099 records, people, titles, dates and publication metadata. No
private snapshot was used. It follows the current curated schema and is licensed
under GPL-3.0-only. External record links use invented identifiers.

## Install and generate

Use Python 3.13 and Git. From a macOS or Linux shell:

```bash
git clone https://github.com/knutzk/glance-analysis-lister.git
cd glance-analysis-lister
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-docs.txt
analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/publication-curation.toml \
  --output-dir pages/demo
cp examples/demo/index.md pages/demo/index.md
cp docs/stylesheets/site.css pages/demo/assets/site.css
```

If you already have a checkout and environment, start with the install command.
Installation needs internet access; generation and preview use only local data.
`python -m analysis_lister` is equivalent to `analysis-lister`.

The explicit [DEMO policy](demo/publication-curation.toml) selects publications
matching `DEMO`, so this workflow produces no missing-policy warning.

## Preview or build

From the repository root, with the same environment active:

```bash
python -m zensical serve -f zensical-demo.toml --dev-addr 127.0.0.1:8001
```

Open <http://127.0.0.1:8001/> and use the navigation to visit all four pages.
Stop the server with **Ctrl+C**. Port 8001 allows the demo to run alongside the
[documentation preview](../docs/site.md) on port 8000. In a new terminal,
run `source .venv/bin/activate` again.

To build static HTML instead:

```bash
python -m zensical build -f zensical-demo.toml --clean --strict
```

The [demo configuration](../zensical-demo.toml) loads the generated browser assets,
enables instant navigation and provides light/dark mode. The copied site stylesheet
is shared with the documentation site and contains its theme adjustments. Run
only one demo build or preview at a time.

| Output | Contents |
| --- | --- |
| `pages/demo/index.md` | Copied demo overview. |
| `pages/demo/ongoing.md` | Four analyses with overlapping subgroups, keywords and different review stages. |
| `pages/demo/papers.md` | Two papers with DOIs and two submitted papers without DOIs, shown as **Under review**. |
| `pages/demo/confnotes.md`, `pages/demo/pubnotes.md` | Four notes per page, including one superseded note hidden by default. |
| `pages/demo/assets/` | CSS and JavaScript for styling and interaction. |
| `pages/demo/view-report.json` | Selection decisions, provenance and diagnostics for the invented records; also copied into the standalone site. |
| `site-demo/` | Built standalone HTML and assets. |

Generation writes into `pages/demo/`; it does not change the fixture or policy.
For your own site, follow [browser asset integration](../docs/rendering.md#enable-browser-assets).

## Tutorial: change publication selection

Keep the tracked example intact and experiment with a policy copy:

```bash
cp examples/demo/publication-curation.toml pages/demo-policy.toml
```

Edit `pages/demo-policy.toml` so all three selection lists are empty:

```toml
[groups.DEMO]
title = "Synthetic demo"
groups = []
subgroups = []
keywords = []
```

Regenerate using that copy:

```bash
analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config pages/demo-policy.toml \
  --output-dir pages/demo
```

The running preview reloads the generated pages. If you stopped it, run the
preview command again. Each publication page now has no selected records, while
the ongoing page still shows four analyses. Publication policy and ongoing-analysis
membership are independent. An explicit empty policy does not trigger fallback
selection or a missing-policy warning.

Restore the original result by rerunning the render command from **Install and
generate**, with `--curation-config examples/demo/publication-curation.toml`.
All four pages return to four records each; note pages initially show the three
non-superseded notes. The documentation site's demo continues
to use the tracked policy; experiments in `pages/demo-policy.toml` affect only the
standalone demo.

## Optional: see missing-policy fallback

To demonstrate missing configuration separately, omit `--curation-config` and
write to another directory:

```bash
analysis-lister render-group --group DEMO \
  --snapshot examples/synthetic_registry.json --output-dir pages/demo-fallback
```

The bundled shared policies have no `DEMO` entry, so this command warns on stderr
and selects publications by the `DEMO` token in their identifiers. See
[publication policies](../docs/rendering.md#publication-policies) for the distinction
between missing and explicitly empty configuration.

The [README screenshots](../docs/images/README.md) use the same synthetic fixture.
