# Synthetic example

Run a complete local site without CERN access, or explore the same records in
the documentation site's **Demo** section. The [demo overview](demo/index.md)
suggests an interaction to try on each page.

[`synthetic_registry.json`](synthetic_registry.json) contains independently
invented DEMO-2099 records, people, titles, dates and publication metadata. No
private snapshot was used. It follows the current curated schema and is licensed
under GPL-3.0-only. External record links use invented identifiers.

## Start the demo

If you followed the [main README quick start](../README.md#install-and-try-without-credentials),
you already have this demo and its environment. Open <http://127.0.0.1:8001/>
while the preview is running, then continue with the
[policy tutorial](#tutorial-change-publication-selection) below.

Starting fresh? Use Python 3.13 and Git in a macOS or Linux shell:

```bash
git clone https://github.com/knutzk/glance-analysis-lister.git
cd glance-analysis-lister
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-docs.txt

mkdir -p examples/demo/work
cp examples/demo/publication-curation.toml examples/demo/work/demo-policy.toml

analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/work/demo-policy.toml \
  --output-dir examples/demo/work/pages

cp examples/demo/index.md examples/demo/work/pages/index.md
cp docs/stylesheets/site.css examples/demo/work/pages/assets/site.css

python -m zensical serve -f examples/demo/zensical.toml --dev-addr 127.0.0.1:8001
```

Both guides use **the same `.venv` and `requirements-docs.txt`**. These requirements
install the package plus Zensical; `pip install .` or `requirements.txt` alone
installs the package without the preview tool. If you already have a checkout
and environment, activate it and start with the requirements install above.
Installation needs internet access; generation and preview use only local data.

**Open <http://127.0.0.1:8001/>.** The demo overview links to all four pages.
Stop the server with **Ctrl+C**. In a new terminal, change to the repository root
and run `source .venv/bin/activate` before running the preview command again.
Port 8001 allows the demo to run alongside the
[documentation preview](../docs/site.md) on port 8000.

The setup commands create `examples/demo/work/pages/index.md`, the browser assets and an
editable `examples/demo/work/demo-policy.toml`. The policy copy initially selects publications
matching `DEMO`, so there is no missing-policy warning. Rerunning the setup's
policy-copy command replaces any edits with the tracked example policy.

The standalone demo configuration, [`demo/zensical.toml`](demo/zensical.toml),
lives beside its landing page and publication policy in `examples/demo/`.
The root `zensical.toml` configures the package documentation site.
Run the commands above from the repository root. Use a Git checkout or unpacked source
distribution for this guide; the installed package alone does not supply the
demo's site configuration and source files.

## Reopen or build the demo

To reopen an already-generated demo, activate the same environment and serve it:

```bash
source .venv/bin/activate
python -m zensical serve -f examples/demo/zensical.toml --dev-addr 127.0.0.1:8001
```

To build static HTML from those generated files instead:

```bash
python -m zensical build -f examples/demo/zensical.toml --clean --strict
```

Generated pages, the editable policy and built HTML stay in the ignored
`examples/demo/work/` directory, outside the maintained demo sources.

The configuration enables instant navigation and light/dark mode, using the
copied browser assets and site stylesheet. Run only one demo build or preview at
a time. The tutorial's render command can update pages while the preview runs.

| Output | Contents |
| --- | --- |
| `examples/demo/work/pages/index.md` | Copied demo overview. |
| `examples/demo/work/pages/ongoing.md` | Four analyses with overlapping subgroups, keywords and different review stages. |
| `examples/demo/work/pages/papers.md` | Two papers with DOIs and two submitted papers without DOIs, shown as **Under review**. |
| `examples/demo/work/pages/confnotes.md`, `examples/demo/work/pages/pubnotes.md` | Four notes per page, including one superseded note hidden by default. |
| `examples/demo/work/pages/assets/` | CSS and JavaScript for styling and interaction. |
| `examples/demo/work/pages/view-report.json` | Selection decisions, provenance and diagnostics for the invented records; also copied into the standalone site. |
| `examples/demo/work/demo-policy.toml` | Editable policy copied during setup. |
| `examples/demo/work/site/` | Built standalone HTML and assets. |

Generation writes into `examples/demo/work/pages/`; it does not change the tracked fixture or
policy. Edit the policy copy, not the generated Markdown, which is replaced
when you rerun `render-group`. Restarting Zensical only serves the existing pages.
For your own site, follow [browser asset integration](../docs/rendering.md#enable-browser-assets).

## Tutorial: change publication selection

Complete **Start the demo** first, including the policy-copy command:

```bash
cp examples/demo/publication-curation.toml examples/demo/work/demo-policy.toml
```

That creates `examples/demo/work/demo-policy.toml` without changing the tracked example.
Skip the copy if the file already contains edits you want to keep.
If the preview is still running, use a second terminal in the repository root
with `source .venv/bin/activate` to run the commands below.

Edit `examples/demo/work/demo-policy.toml` so all three selection lists are empty:

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
  --curation-config examples/demo/work/demo-policy.toml \
  --output-dir examples/demo/work/pages
```

The running preview reloads the generated pages. If you stopped it, run the
preview command again. Each publication page now has no selected records, while
the ongoing page still shows four analyses. Publication policy and ongoing-analysis
membership are independent. An explicit empty policy does not trigger fallback
selection or a missing-policy warning.

Restore the original example policy and regenerate:

```bash
cp examples/demo/publication-curation.toml examples/demo/work/demo-policy.toml

analysis-lister render-group --group DEMO --group-title "Synthetic demo" \
  --snapshot examples/synthetic_registry.json \
  --curation-config examples/demo/work/demo-policy.toml \
  --output-dir examples/demo/work/pages
```

This explicitly replaces your edits in `examples/demo/work/demo-policy.toml`. All four pages
return to four records each; note pages initially show the three non-superseded
notes. The documentation site's demo continues to use the tracked policy;
experiments in `examples/demo/work/demo-policy.toml` affect only the standalone demo.

## Optional: see missing-policy fallback

To demonstrate missing configuration separately, omit `--curation-config` and
write to another directory:

```bash
analysis-lister render-group --group DEMO \
  --snapshot examples/synthetic_registry.json --output-dir examples/demo/work/pages-fallback
```

The bundled shared policies have no `DEMO` entry, so this command warns on stderr
and selects publications by the `DEMO` token in their identifiers. See
[publication policies](../docs/rendering.md#publication-policies) for the distinction
between missing and explicitly empty configuration.

The [README screenshots](../docs/images/README.md) use the same synthetic fixture.
