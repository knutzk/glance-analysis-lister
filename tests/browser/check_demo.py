# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise the documented demo, policy tutorial and documentation integration."""

import argparse
import functools
import json
import runpy
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import URLError
from urllib.request import urlopen

from bs4 import BeautifulSoup
from check_zensical import SiteHandler, browse

ROOT = Path(__file__).resolve().parents[2]
POLICY = "examples/demo/publication-curation.toml"


def wait_for_preview_text(url, text):
    deadline = time.monotonic() + 15
    while True:
        with urlopen(url, timeout=5) as response:
            if text in response.read().decode():
                return
        assert time.monotonic() < deadline, f"Preview did not reload: {url}"
        time.sleep(0.1)


def render(work, policy, publications):
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("analysis-lister")),
            "render-group",
            "--group",
            "DEMO",
            "--group-title",
            "Synthetic demo",
            "--snapshot",
            "examples/synthetic_registry.json",
            "--curation-config",
            policy,
            "--output-dir",
            "pages/demo",
        ],
        cwd=work,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No publication curation configuration" not in result.stdout + result.stderr
    report = json.loads((work / "pages/demo/view-report.json").read_text())
    assert report["counts"]["ongoing_analyses"] == 4
    assert report["counts"]["archive_publications"] == publications
    assert report["counts"]["warning_issues"] == 0


@contextmanager
def preview(work, *, documentation=False):
    """Start and stop the actual documented Zensical preview command."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base = f"http://127.0.0.1:{port}/"
    if documentation:
        base += "glance-analysis-lister/"
    command = (
        [sys.executable, "scripts/docs.py", "serve"]
        if documentation
        else [sys.executable, "-m", "zensical", "serve", "-f", "zensical-demo.toml"]
    )
    log_path = work / "preview.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [*command, "--dev-addr", f"127.0.0.1:{port}"],
            cwd=work,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise AssertionError(log_path.read_text())
                try:
                    with urlopen(base, timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            yield base
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            with socket.socket() as connection:
                connection.settimeout(1)
                assert connection.connect_ex(("127.0.0.1", port)) != 0, (
                    "Preview left its server running after termination"
                )


def check_demo(work, driver):
    # The same allowlist used for documentation keeps private inputs out of tests.
    public = runpy.run_path(str(ROOT / "scripts/docs.py"))["PUBLIC_FILES"]
    for name in public:
        destination = work / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    fixture = (work / "examples/synthetic_registry.json").read_bytes()
    original_policy = (work / POLICY).read_text()
    render(work, POLICY, 12)
    shutil.copyfile(work / "examples/demo/index.md", work / "pages/demo/index.md")
    shutil.copyfile(
        work / "docs/stylesheets/site.css", work / "pages/demo/assets/site.css"
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "zensical",
            "build",
            "-f",
            "zensical-demo.toml",
            "--clean",
            "--strict",
        ],
        cwd=work,
        check=True,
    )

    # Follow the policy-copy tutorial, then restore the default result.
    edited = original_policy.replace('groups = ["DEMO"]', "groups = []")
    assert edited != original_policy
    (work / "pages/demo-policy.toml").write_text(edited)
    render(work, "pages/demo-policy.toml", 0)
    render(work, POLICY, 12)
    assert (work / POLICY).read_text() == original_policy
    assert (work / "examples/synthetic_registry.json").read_bytes() == fixture
    with preview(work) as base:
        browse(base, driver, page_prefix="")

    # Local roadmap preview must not require edits to the tracked config or leak
    # into a subsequent public build. Use invented text, never a local roadmap.
    config_before = (work / "zensical.toml").read_bytes()
    roadmap = work / "ROADMAP.md"
    roadmap.write_text("# Local roadmap preview\n\n- [ ] Invented task\n")
    with preview(work, documentation=True) as base:
        with urlopen(base + "ROADMAP/", timeout=5) as response:
            assert "Local roadmap preview" in response.read().decode()
        roadmap.write_text(roadmap.read_text() + "\nUpdated local planning text.\n")
        wait_for_preview_text(base + "ROADMAP/", "Updated local planning text.")
        notes = work / ".github/release-notes/v0.2.0.txt"
        original_notes = notes.read_bytes()
        notes.write_bytes(
            original_notes + b"\n\nSynthetic release-note reload check.\n"
        )
        wait_for_preview_text(
            base + "docs/release-notes/v0.2.0/", "Synthetic release-note reload check."
        )
        notes.write_bytes(original_notes)
    assert (work / "zensical.toml").read_bytes() == config_before

    # Build the documentation site with the complete demo under its real subpath.
    subprocess.run([sys.executable, "scripts/docs.py", "build"], cwd=work, check=True)
    assert not (work / "site-src/ROADMAP.md").exists()
    assert not (work / "site/ROADMAP").exists()
    assert 'href="ROADMAP/' not in (work / "site/index.html").read_text()
    assert not list((work / "site-src").rglob("view-report.json"))
    assert not (work / "site-src/.github").exists()
    for version in ("v0.1.0", "v0.2.0"):
        original = (work / f".github/release-notes/{version}.txt").read_bytes()
        staged = (work / f"site-src/docs/release-notes/{version}.md").read_bytes()
        assert staged.endswith(original), "Release notes must reuse the maintained text"
        html = (work / f"site/docs/release-notes/{version}/index.html").read_text()
        assert "Synthetic release-note reload check." not in html
        assert (
            BeautifulSoup(html, "html.parser")
            .h1.get_text()
            .startswith(f"{version} release notes")
        )
    for guide in ("ongoing", "publications"):
        html = (work / "site/docs" / guide / "index.html").read_text()
        records = BeautifulSoup(html, "html.parser").select(
            ".gal-doc-example [data-gal-item]"
        )
        assert len(records) == 1, "Explanatory guides should show one record"
        assert records[0]["id"].endswith("demo-2099-01")
    served = work / "served"
    served.mkdir()
    (served / "glance-analysis-lister").symlink_to(
        work / "site", target_is_directory=True
    )
    with ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(SiteHandler, directory=str(served)),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/glance-analysis-lister/"
            browse(
                base,
                driver,
                page_prefix="examples/demo/",
                start_page="examples/demo/",
            )
        finally:
            server.shutdown()
            thread.join()
    print(
        "Demo checks passed: standalone preview, policy tutorial, local roadmap isolation and documentation demo."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="glance-demo-check-") as directory:
        check_demo(Path(directory), args.driver)


if __name__ == "__main__":
    main()
