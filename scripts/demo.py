# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Prepare and preview the public synthetic demo from a source checkout."""

import argparse
import importlib
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "analysis_lister/__init__.py").is_file():
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "build", "prepare"))
    parser.add_argument("--dev-addr", default="127.0.0.1:8001")
    parser.add_argument(
        "--reset-policy",
        action="store_true",
        help="Replace the editable demo policy with the original example policy.",
    )
    args = parser.parse_args()
    # Check the environment and source files before touching existing outputs.
    try:
        importlib.import_module("zensical")
        importlib.import_module("analysis_lister.views.build")
    except ModuleNotFoundError as error:
        parser.exit(
            1,
            f"Missing demo dependency: {error.name}\n"
            f"Python environment: {sys.executable}\n"
            "From the repository root, install the demo/documentation requirements:\n"
            f"  {shlex.quote(sys.executable)} -m pip install -r requirements-docs.txt\n"
            "Or activate the prepared environment: source .venv/bin/activate\n",
        )
    for name in (
        "zensical-demo.toml",
        "examples/synthetic_registry.json",
        "examples/demo/publication-curation.toml",
        "examples/demo/index.md",
        "docs/stylesheets/site.css",
    ):
        if not (ROOT / name).is_file():
            parser.exit(1, f"Incomplete source checkout: missing {ROOT / name}\n")

    policy = ROOT / "pages/demo-policy.toml"
    policy.parent.mkdir(parents=True, exist_ok=True)
    if args.reset_policy or not policy.exists():
        shutil.copyfile(ROOT / "examples/demo/publication-curation.toml", policy)
    result = subprocess.call(
        [
            sys.executable,
            "-m",
            "analysis_lister",
            "render-group",
            "--group",
            "DEMO",
            "--group-title",
            "Synthetic demo",
            "--snapshot",
            "examples/synthetic_registry.json",
            "--curation-config",
            "pages/demo-policy.toml",
            "--output-dir",
            "pages/demo",
        ],
        cwd=ROOT,
    )
    if result:
        return result
    shutil.copyfile(ROOT / "examples/demo/index.md", ROOT / "pages/demo/index.md")
    shutil.copyfile(
        ROOT / "docs/stylesheets/site.css", ROOT / "pages/demo/assets/site.css"
    )
    print(f"Editable demo policy: {policy}", flush=True)
    if args.command == "prepare":
        return 0
    command = [
        sys.executable,
        "-m",
        "zensical",
        args.command,
        "-f",
        "zensical-demo.toml",
    ]
    if args.command == "build":
        return subprocess.call([*command, "--clean", "--strict"], cwd=ROOT)
    print(f"Open http://{args.dev_addr}/ — stop with Ctrl+C.", flush=True)
    # Replace the launcher so stopping it also stops the preview server.
    os.chdir(ROOT)
    return os.execv(sys.executable, [*command, "--dev-addr", args.dev_addr])


if __name__ == "__main__":
    raise SystemExit(main())
