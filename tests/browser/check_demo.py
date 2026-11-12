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
import tomllib
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

from bs4 import BeautifulSoup
from check_zensical import SiteHandler, browse
from timing import timed

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
    if command[0] == "grove":
        return [str(Path(sys.executable).with_name("grove")), *command[1:]]
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
        base += "glance-grove/"
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


@timed("check_local_group_preview")
def check_local_group_preview(work, driver):
    # TOPQ is a navigation label in this test; all records remain invented DEMO data.
    run_commands(
        work,
        [
            [
                "grove",
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
            exhaustive=False,
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


@timed("check_demonstrator_group")
def check_demonstrator_group(work, driver):
    """Follow the CERN guide's navigation/render handoff with invented data only."""
    section = (work / "docs/cern-demo.md").read_text()
    commands = bash_blocks(section)
    render = commands[1][1].copy()
    assert render[:2] == ["grove", "render-group"]
    assert render[render.index("--group") + 1] == "TOPQ"
    # Exercise the real documented destination, but never download/read CERN data.
    render[render.index("--group") + 1] = "DEMO"
    render[render.index("--snapshot") + 1] = "examples/synthetic_registry.json"
    render.extend(["--curation-config", POLICY])
    run_commands(work, [render])
    assert commands[2][0] == quickstart_commands(work)[-1]

    config = work / "examples/demo/work/zensical.toml"
    nav = re.search(r"```toml\n(.*?)```", section, re.S).group(1).strip()
    tomllib.loads(nav)
    config.write_text(
        re.sub(
            r"nav = \[.*?\n\]", lambda _: nav, config.read_text(), count=1, flags=re.S
        )
    )
    tomllib.loads(config.read_text())
    original = work / "examples/demo/zensical.toml"
    assert "TOPQ" not in original.read_text(), "Only the local copy may change"
    with preview(work) as base:
        with urlopen(base, timeout=5) as response:
            html = response.read().decode()
        assert "TOPQ (CERN data)" in html
        links = {
            urljoin(base, link["href"])
            for link in BeautifulSoup(html, "html.parser").select("a[href]")
        }
        assert {base + "papers/", base + "topq/papers/"} <= links, links
        browse(
            base,
            driver,
            page_prefix="topq/",
            start_page="topq/papers/",
            exhaustive=False,
        )
        ongoing = work / "examples/demo/work/pages/topq/ongoing.md"
        ongoing.write_text(
            ongoing.read_text() + "\nStandalone group reload sentinel.\n"
        )
        wait_for_preview_text(
            base + "topq/ongoing/", "Standalone group reload sentinel."
        )
    check_outputs(work, 12)
    run_commands(
        work,
        [
            [
                "python",
                "-m",
                "zensical",
                "build",
                "-f",
                "examples/demo/work/zensical.toml",
                "--clean",
                "--strict",
            ]
        ],
    )
    assert (work / "examples/demo/work/site/topq/papers/index.html").is_file()


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
        browse(base, driver, page_prefix="", exhaustive=False)

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
            assert not html.select("[data-grove-item], [data-grove-note]")
        run_commands(work, tutorial[2])
        check_outputs(work, 12)
        wait_for_preview_text(base + "papers/", "data-grove-item")
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
    check_demonstrator_group(work, driver)

    # Documentation previews reload source edits without changing tracked config.
    config_before = (work / "zensical.toml").read_bytes()
    with preview(work, documentation=True) as base:
        guide = work / "docs/contributing.md"
        original_guide = guide.read_bytes()
        guide.write_bytes(
            original_guide + b"\n\nSynthetic contributor-guide reload check.\n"
        )
        wait_for_preview_text(
            base + "docs/contributing/", "Synthetic contributor-guide reload check."
        )
        guide.write_bytes(original_guide)
    assert (work / "zensical.toml").read_bytes() == config_before

    # Build the documentation site with the complete demo under its real subpath.
    subprocess.run([sys.executable, "scripts/docs.py", "build"], cwd=work, check=True)
    assert not list((work / "site-src").rglob("view-report.json"))
    assert not (work / "site-src/.github").exists()
    assert not (work / "site/examples/demo/work").exists()
    assert not (work / "site-src/examples/demo/work").exists()
    assert not (work / "site/docs/release-notes").exists()
    for page in ("file-reference", "python-access", "upgrading", "contributing"):
        html = (work / f"site/docs/{page}/index.html").read_text()
        assert BeautifulSoup(html, "html.parser").h1 is not None
        assert "Synthetic contributor-guide reload check." not in html
    html = (work / "site/docs/pages/index.html").read_text()
    records = BeautifulSoup(html, "html.parser").select(
        ".grove-doc-example [data-grove-item]"
    )
    assert {record["id"] for record in records} == {
        "analysis-demo-ana-demo-2099-01",
        "publication-papers-demo-demo-2099-01",
    }, "The page guide must retain both interactive examples without duplicate IDs"
    for removed in (
        "architecture",
        "contributing-field",
        "development",
        "documentation",
        "releases",
        "compatibility",
        "glossary",
        "curated-format",
        "output-reference",
        "ongoing",
        "publications",
        "registry",
        "rendering",
        "workflows",
        "diagnostics",
        "provenance",
        "troubleshooting",
        "site",
    ):
        assert not (work / "site/docs" / removed).exists()
    served = work / "served"
    served.mkdir()
    (served / "glance-grove").symlink_to(work / "site", target_is_directory=True)
    with ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(SiteHandler, directory=str(served)),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/glance-grove/"
            # Keep the full suite on the real documentation theme and project CSS,
            # in addition to the minimal host exercised by check_zensical.py.
            browse(
                base,
                driver,
                page_prefix="examples/demo/",
                start_page="examples/demo/",
                exhaustive=True,
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
    with timed("check_demo"):
        main()
