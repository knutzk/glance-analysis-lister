# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise the documented demo, policy tutorial and documentation integration."""

import argparse
import functools
import json
import re
import runpy
import shlex
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


def check_outputs(work, publications):
    report = json.loads(
        (work / "examples/demo/work/pages/view-report.json").read_text()
    )
    assert report["counts"]["ongoing_analyses"] == 4
    assert report["counts"]["archive_publications"] == publications
    assert report["counts"]["warning_issues"] == 0
    assert (work / "examples/demo/work/pages/index.md").read_bytes() == (
        work / "examples/demo/index.md"
    ).read_bytes()
    assert (work / "examples/demo/work/pages/assets/site.css").read_bytes() == (
        work / "docs/stylesheets/site.css"
    ).read_bytes()
    assert (work / "examples/demo/work/demo-policy.toml").is_file()


def bash_blocks(text):
    return [
        [
            command
            for line in block.replace("\\\n", "").splitlines()
            if (command := shlex.split(line, comments=True))
        ]
        for block in re.findall(r"```bash\n(.*?)```", text, re.S)
    ]


def executable(command):
    if command[0] == "python":
        return [sys.executable, *command[1:]]
    if command[0] == "analysis-lister":
        return [str(Path(sys.executable).with_name("analysis-lister")), *command[1:]]
    assert command[0] in {"mkdir", "cp"}, command
    return command


def quickstart_commands(work):
    # Execute the documented setup, rather than filling in missing files here.
    commands = [
        bash_blocks((work / readme).read_text())[0]
        for readme in ("README.md", "examples/README.md")
    ]
    assert commands[0] == commands[1], "Both entry points must use the same setup"
    install = ["python", "-m", "pip", "install", "-r", "requirements-docs.txt"]
    # CI already installed these dependencies in the active test environment.
    return commands[0][commands[0].index(install) + 1 :]


def run_commands(work, commands):
    for command in commands:
        result = subprocess.run(
            executable(command), cwd=work, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            "No publication curation configuration" not in result.stdout + result.stderr
        )


@contextmanager
def preview(work, *, documentation=False, group_pages=()):
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
        else executable(quickstart_commands(work)[-1])
    )
    if not documentation:
        assert command[-2:] == ["--dev-addr", "127.0.0.1:8001"]
        command = command[:-2]  # Use an available port for this test run.
    for group in group_pages:
        command.extend(["--group-pages", group])
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


def check_local_group_preview(work, driver):
    # TOPQ is a navigation label in this test; all records remain invented DEMO data.
    run_commands(
        work,
        [
            [
                "analysis-lister",
                "render-group",
                "--group",
                "DEMO",
                "--snapshot",
                "examples/synthetic_registry.json",
                "--curation-config",
                POLICY,
                "--output-dir",
                "pages/topq",
            ]
        ],
    )
    group = work / "pages/topq"
    (group / "extra.md").write_text("# Unselected local file\n")
    (group / "cookies.json").write_text('{"sentinel": "invented test input"}')
    local = work / ".cache/docs-group-preview"
    public_before = (work / "site/index.html").read_bytes()
    with preview(
        work,
        documentation=True,
        group_pages=(
            "TOPQ=pages/topq",
            "HIGP=pages/topq",
        ),
    ) as base:
        with urlopen(base, timeout=5) as response:
            html = response.read().decode()
        assert "TOPQ (local data)" in html and "HIGP (local data)" in html
        assert "examples/demo/ongoing/" in html
        assert (work / "site/index.html").read_bytes() == public_before
        staged = local / "site-src/local-groups/topq"
        assert {p.name for p in staged.iterdir()} == {
            "ongoing.md",
            "papers.md",
            "confnotes.md",
            "pubnotes.md",
        }
        assert not list(local.rglob("view-report.json"))
        assert not list(local.rglob("cookies.json"))
        assert not list(local.rglob("extra.md"))
        with urlopen(base + "local-groups/higp/papers/", timeout=5) as response:
            assert response.status == 200
        browse(
            base,
            driver,
            page_prefix="local-groups/topq/",
            start_page="local-groups/topq/papers/",
        )
        ongoing = group / "ongoing.md"
        ongoing.write_text(ongoing.read_text() + "\nLocal group reload sentinel.\n")
        wait_for_preview_text(
            base + "local-groups/topq/ongoing/", "Local group reload sentinel."
        )
    # Reject accidental publication/network exposure and invalid selections before
    # starting the server or clearing any generated directories.
    for command in (
        ["build", "--group-pages", "TOPQ=pages/topq"],
        ["serve", "--group-pages", "TOPQ=pages/missing"],
        ["serve", "--group-pages", "TOPQ=pages/topq", "--dev-addr", "0.0.0.0:8000"],
        ["serve", "--group-pages", "../TOPQ=pages/topq"],
        [
            "serve",
            "--group-pages",
            "TOPQ=pages/topq",
            "--group-pages",
            "TOPQ=pages/topq",
        ],
        [
            "serve",
            "--group-pages",
            "TOPQ=.cache/docs-group-preview/site-src/local-groups/topq",
        ],
    ):
        rejected = subprocess.run(
            [sys.executable, "scripts/docs.py", *command],
            cwd=work,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 2, rejected.stdout + rejected.stderr
    # A normal preview must drop the local sections even while their source and
    # cached HTML still exist. A subsequent public build must contain none of them.
    with preview(work, documentation=True) as base:
        with urlopen(base, timeout=5) as response:
            assert "local-groups/" not in response.read().decode()
        assert not (work / "site-src/local-groups").exists()
    subprocess.run([sys.executable, "scripts/docs.py", "build"], cwd=work, check=True)
    assert not (work / "site/local-groups").exists()
    assert not (work / "site-src/local-groups").exists()
    for html in (work / "site").rglob("*.html"):
        assert "Local group reload sentinel." not in html.read_text()


def check_demo(work, driver):
    # The same allowlist used for documentation keeps private inputs out of tests.
    public = runpy.run_path(str(ROOT / "scripts/docs.py"))["PUBLIC_FILES"]
    for name in public:
        destination = work / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    fixture = (work / "examples/synthetic_registry.json").read_bytes()
    original_policy = (work / POLICY).read_text()
    assert not (work / "examples/demo/work").exists()
    run_commands(work, quickstart_commands(work)[:-1])
    with preview(work) as base:
        check_outputs(work, 12)
        assert (
            work / "examples/demo/work/demo-policy.toml"
        ).read_text() == original_policy
        with urlopen(base, timeout=5) as response:
            homepage = BeautifulSoup(response.read(), "html.parser")
        assert homepage.h1.get_text().strip().startswith("Interactive demo")
        browse(base, driver, page_prefix="")

    # Follow the tutorial's literal commands, including its explicit reset.
    tutorial_text = (
        (work / "examples/README.md")
        .read_text()
        .split("## Tutorial: change publication selection", 1)[1]
        .split("\n## ", 1)[0]
    )
    tutorial = bash_blocks(tutorial_text)
    assert len(tutorial) == 3
    run_commands(work, tutorial[0])
    policy = work / "examples/demo/work/demo-policy.toml"
    edited = policy.read_text().replace('groups = ["DEMO"]', "groups = []")
    assert edited != original_policy
    policy.write_text(edited)
    run_commands(work, tutorial[1])
    check_outputs(work, 0)
    # Restarting the preview must preserve edits and publish the changed result.
    with preview(work) as base:
        check_outputs(work, 0)
        assert policy.read_text() == edited
        for page in ("papers", "confnotes", "pubnotes"):
            with urlopen(base + page + "/", timeout=5) as response:
                html = BeautifulSoup(response.read(), "html.parser")
            assert not html.select("[data-gal-item], [data-gal-note]")
        run_commands(work, tutorial[2])
        check_outputs(work, 12)
        wait_for_preview_text(base + "papers/", "data-gal-item")
    assert policy.read_text() == original_policy
    assert (work / POLICY).read_text() == original_policy
    assert (work / "examples/synthetic_registry.json").read_bytes() == fixture
    # Invalid policy edits must not replace previously rendered pages.
    previous = (work / "examples/demo/work/pages/papers.md").read_bytes()
    policy.write_text("[invalid TOML")
    invalid = subprocess.run(
        executable(tutorial[1][0]),
        cwd=work,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
    assert (work / "examples/demo/work/pages/papers.md").read_bytes() == previous
    policy.write_text(original_policy)
    build_section = (
        (work / "examples/README.md")
        .read_text()
        .split("## Reopen or build the demo", 1)[1]
        .split("\n## ", 1)[0]
    )
    run_commands(work, bash_blocks(build_section)[1])
    assert (work / "examples/demo/work/site/index.html").is_file()

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
    check_local_group_preview(work, driver)
    print(
        "Demo checks passed: standalone/tutorial, documentation and local group preview isolation."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="glance-demo-check-") as directory:
        check_demo(Path(directory), args.driver)


if __name__ == "__main__":
    main()
