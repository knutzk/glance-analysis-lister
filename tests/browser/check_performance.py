# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Measure fresh CLI renders and browser filtering using scaled public demo data."""

import argparse
import functools
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from check_zensical import PAGES, SiteHandler
from performance_fixture import synthetic_registry
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from grove.provenance import generator_fingerprint, generator_revision
from grove.storage import atomic_write_text

ROOT = Path(__file__).resolve().parents[2]

# Browser-side timing excludes WebDriver transport. Two animation frames allow
# layout and a paint opportunity after the event; this is not an INP measurement.
INTERACT = """
const [selector, value, counter, rows, done] = arguments;
const control = document.querySelector(selector);
const start = performance.now();
if (value === null) control.click();
else {
  control.value = value;
  control.dispatchEvent(new Event('input', {bubbles: true}));
}
requestAnimationFrame(() => requestAnimationFrame(() => {
  const elapsed = performance.now() - start;
  done({milliseconds: elapsed,
        counter: document.querySelector(counter).textContent,
        visible: [...document.querySelectorAll(rows)].filter(e => !e.hidden).length});
}));
"""


def summary(samples):
    return {
        "samples": samples,
        "median": statistics.median(samples),
        "max": max(samples),
    }


def render_and_build(work, records, repeats):
    snapshot = work / "synthetic_registry.json"
    raw = (json.dumps(synthetic_registry(records), indent=2) + "\n").encode()
    snapshot.write_bytes(raw)
    samples = []
    for repeat in range(repeats):
        output = work / f"render-{repeat}"
        start = time.perf_counter()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "grove",
                "render-group",
                "--group",
                "DEMO",
                "--snapshot",
                str(snapshot),
                "--curation-config",
                str(ROOT / "examples/demo/publication-curation.toml"),
                "--output-dir",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        samples.append(time.perf_counter() - start)
        report = json.loads((output / "view-report.json").read_text())
        assert report["counts"]["ongoing_analyses"] == records
        assert report["counts"]["archive_publications"] == 3 * records
        assert report["counts"]["warning_issues"] == 0
    page_bytes = {page: (output / f"{page}.md").stat().st_size for page in PAGES}
    (output / "view-report.json").unlink()
    assets = ("common", "ongoing", "papers", "notes")
    config = (
        f"site_name: Synthetic performance check\ndocs_dir: {output.name}\n"
        "site_url: http://127.0.0.1/\ntheme:\n  name: material\n  font: false\n"
        "nav:\n"
        + "".join(f"  - {page}: {page}.md\n" for page in PAGES)
        + "extra_css:\n"
        + "".join(f"  - assets/gal-{name}.css\n" for name in assets)
        + "extra_javascript:\n"
        + "".join(f"  - assets/gal-{name}.js\n" for name in assets)
    )
    (work / "mkdocs.yml").write_text(config)
    subprocess.run(
        [sys.executable, "-m", "zensical", "build", "--strict"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "records_per_category": records,
        "total_records": records * 4,
        "snapshot_bytes": len(raw),
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "markdown_bytes": page_bytes,
        "html_bytes": {
            page: (work / "site" / page / "index.html").stat().st_size for page in PAGES
        },
    }, summary(samples)


def browse(work, driver_path, base, records, repeats):
    options = Options()
    if chrome := os.environ.get("CHROME_BINARY"):
        options.binary_location = chrome
    for flag in (
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-extensions",
        "--window-size=1280,900",
    ):
        options.add_argument(flag)
    service = Service(str(driver_path), log_output=str(work / "chromedriver.log"))
    pages = {}
    with webdriver.Chrome(options=options, service=service) as driver:
        driver.set_script_timeout(60)
        driver.set_page_load_timeout(120)
        environment = {
            "chrome": driver.capabilities["browserVersion"],
            "chromedriver": driver.capabilities["chrome"]["chromedriverVersion"],
        }
        assert (
            environment["chrome"].split(".")[:3]
            == environment["chromedriver"].split(".")[:3]
        ), "Use matching Chrome and ChromeDriver builds"
        for page in PAGES:
            notes = page in {"confnotes", "pubnotes"}
            counter = "[data-gal-note-count]" if notes else "[data-gal-count]"
            rows = "[data-gal-note]" if notes else "[data-gal-item]"
            reset = "[data-gal-note-reset]" if notes else "[data-gal-reset]"
            default = records * 3 // 4 if notes else records
            start = time.perf_counter()
            driver.get(base + page + "/")
            WebDriverWait(driver, 60).until(
                lambda d, notes=notes: d.execute_script(
                    "return !!document.querySelector(arguments[0]) && "
                    "!document.querySelector(arguments[0]).hidden && "
                    "document.querySelector('[data-gal-search]').getClientRects().length > 0",
                    "[data-gal-note-controls]" if notes else "[data-gal-controls]",
                )
            )
            ready = time.perf_counter() - start
            assert (
                driver.execute_script(
                    "return document.querySelectorAll(arguments[0]).length", rows
                )
                == records
            )
            category = (
                '[data-gal-note-supersession="superseded"]'
                if notes
                else '[data-gal-value="DEMO-Tracking"]'
                if page == "ongoing"
                else '[data-gal-value="published"]'
            )
            actions = (
                ("search-half", "[data-gal-search]", "Tracking", records // 2),
                ("search-none", "[data-gal-search]", "no-synthetic-record-matches", 0),
                ("reset-search", reset, None, default),
                ("category", category, None, records if notes else records // 2),
                ("reset-category", reset, None, default),
            )
            timings = {name: [] for name, *_ in actions}
            for _ in range(repeats):
                for name, selector, value, expected in actions:
                    result = driver.execute_async_script(
                        INTERACT, selector, value, counter, rows
                    )
                    assert result["visible"] == expected, (page, name, result)
                    assert result["counter"].startswith(f"{expected} of {records} "), (
                        result
                    )
                    timings[name].append(result["milliseconds"])
            pages[page] = {
                "webdriver_ready_seconds": ready,
                "filter_milliseconds": {
                    name: summary(values) for name, values in timings.items()
                },
            }
        environment["viewport"] = driver.execute_script(
            "return {width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio}"
        )
    return environment, pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver",
        type=Path,
        required=True,
        help="Existing ChromeDriver; never downloaded.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSON evidence report, written even if a timing limit fails.",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=1000,
        help="Per category; a positive multiple of four (default: 1000).",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--render-limit",
        type=float,
        default=30,
        help="Maximum seconds per fresh CLI render.",
    )
    parser.add_argument(
        "--filter-limit",
        type=float,
        default=500,
        help="Maximum milliseconds per browser filter action.",
    )
    args = parser.parse_args()
    if args.records < 4 or args.records % 4 or args.repeats < 1:
        parser.error(
            "--records must be a positive multiple of four and --repeats positive"
        )
    if not (
        0 < args.render_limit < float("inf") and 0 < args.filter_limit < float("inf")
    ):
        parser.error("Limits must be finite positive numbers")
    with TemporaryDirectory(prefix="glance-performance-") as directory:
        work = Path(directory)
        dataset, rendering = render_and_build(work, args.records, args.repeats)
        with ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(SiteHandler, directory=str(work / "site")),
        ) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                browser, pages = browse(
                    work,
                    args.driver,
                    f"http://127.0.0.1:{server.server_port}/",
                    args.records,
                    args.repeats,
                )
            finally:
                server.shutdown()
                thread.join()
    failures = []
    if rendering["max"] > args.render_limit:
        failures.append("rendering")
    for page, result in pages.items():
        for action, timing in result["filter_milliseconds"].items():
            if timing["max"] > args.filter_limit:
                failures.append(f"{page}/{action}")
    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "generator_revision": generator_revision(),
        "generator_sha256": generator_fingerprint(),
        "benchmark_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
            + Path(__file__).with_name("performance_fixture.py").read_bytes()
        ).hexdigest(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "dependencies": {
                name: version(name)
                for name in (
                    "glance-grove",
                    "zensical",
                    "selenium",
                    "attrs",
                    "jsonschema",
                )
            },
            **browser,
        },
        "dataset": dataset,
        "render_seconds": rendering,
        "pages": pages,
        "provisional_limits": {
            "render_seconds": args.render_limit,
            "filter_milliseconds": args.filter_limit,
        },
        "failures": failures,
    }
    atomic_write_text(args.output, json.dumps(report, indent=2) + "\n")
    print(
        f"Performance report: {args.output}; fresh render max {rendering['max']:.3f} s"
    )
    for page, result in pages.items():
        maximum = max(item["max"] for item in result["filter_milliseconds"].values())
        print(f"  {page}: filter max {maximum:.1f} ms")
    if failures:
        raise SystemExit("Provisional limits exceeded: " + ", ".join(failures))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stdout + error.stderr) from None
