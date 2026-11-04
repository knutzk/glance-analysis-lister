# Regenerate the screenshots

The documentation images are browser captures of the Zensical views built from [`examples/synthetic_registry.json`](../../examples/synthetic_registry.json).
They use an explicit DEMO publication policy and only independently invented
data.

From the repository root, with Python 3.13, Chrome and a compatible ChromeDriver:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -r tests/browser/requirements.txt
python scripts/capture_screenshots.py --driver /path/to/chromedriver
```

Set `CHROME_BINARY` to select a different Chrome executable. For environment
setup, see [development and validation](../development.md).

The script builds a strict temporary site, runs the Zensical browser checks,
expands each view and captures it at a 1440-pixel browser width. It extends the
viewport height to fit the content. Browser and font differences can change the
pixels.

The script replaces four PNGs: the full `ongoing.png` and `papers.png` views,
and the focused `ongoing-card.png` and `publication-row.png` fallbacks shown when
reading the guides on GitHub. The documentation site replaces those fallbacks
with live rendered examples. Temporary pages and reports are removed. Inspect
the images before committing them. The fixtures and capture script are
GPL-3.0-only; the site uses Zensical's built-in theme.
