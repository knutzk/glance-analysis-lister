# Regenerate the screenshots

The four PNG screenshots are browser captures of the Zensical views built from [`examples/synthetic_registry.json`](../../examples/synthetic_registry.json).
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

[`command-flow.svg`](command-flow.svg) is a hand-maintained vector diagram used
in the main README. Edit the SVG directly; it is not produced by the screenshot
script. Keep snapshots visually distinct from commands, center the `refresh`
caption, and preserve the equal connector gaps and the output-to-preview turn.
Inspect the rendered README at desktop width with both navigation columns, in
light and dark mode, after changing it.
