# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Advisory comparison of the explicitly documented Python surface."""

import argparse
import importlib
import inspect
import io
import itertools
import json
import os
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SURFACE = Path("scripts/public_api.toml")
EMPTY = inspect.Parameter.empty


def resolve(target, root):
    module, name = target.split(":")
    try:
        value = importlib.import_module(module)
    except ModuleNotFoundError as error:
        if error.name and (error.name == module or module.startswith(error.name + ".")):
            return None, None
        raise  # Missing dependencies are tool failures, not removed public APIs.
    # A removed package/module must not resolve to the installed candidate (or
    # an editable checkout) while inspecting a different revision.
    origin = getattr(value, "__file__", None)
    locations = [origin] if origin else getattr(value, "__path__", ())
    if not any(
        Path(location).resolve().is_relative_to(root.resolve())
        for location in locations
    ):
        return None, None
    parent = None
    for part in name.split("."):
        parent = value
        if not hasattr(parent, part):
            return None, parent
        value = getattr(parent, part)
    receiver = (
        inspect.isclass(parent)
        and inspect.isfunction(value)
        and not isinstance(inspect.getattr_static(parent, part), staticmethod)
    )
    return value, receiver


def signature(value, receiver=False):
    parameters = list(inspect.signature(value).parameters.values())
    if receiver:
        parameters = parameters[1:]  # Instance receiver; classmethods are bound.
    return [
        {
            "name": p.name,
            "kind": p.kind.name,
            "required": p.default is EMPTY,
            "default": None if p.default is EMPTY else repr(p.default),
        }
        for p in parameters
    ]


def snapshot(surface, root):
    result = {
        "callables": {},
        "constants": {},
        "attributes": {},
        "imports": {**surface["callables"], **surface["constants"]},
    }
    for name, target in surface["callables"].items():
        value, receiver = resolve(target, root)
        result["callables"][name] = (
            signature(value, receiver) if callable(value) else None
        )
    for name, target in surface["constants"].items():
        value, _ = resolve(target, root)
        result["constants"][name] = {"present": value is not None, "value": value}
    for name, item in surface["attributes"].items():
        value, _ = resolve(item["target"], root)
        # attrs fields and ordinary properties are class descriptors. Annotations
        # also describe non-slotted fields; their types are not frozen here.
        annotations = getattr(value, "__annotations__", {})
        for field in item["names"]:
            result["attributes"][f"{name}.{field}"] = value is not None and (
                hasattr(value, field) or field in annotations
            )
    return result


def as_signature(parameters):
    return inspect.Signature(
        [
            inspect.Parameter(
                p["name"],
                getattr(inspect.Parameter, p["kind"]),
                default=EMPTY if p["required"] else p["default"],
            )
            for p in parameters
        ]
    )


def signature_issues(before, after):
    old, new = as_signature(before), as_signature(after)
    fixed = [
        p
        for p in old.parameters.values()
        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]
    if len(fixed) > 10:
        raise ValueError("Public signature exceeds the bounded call-probe limit")
    issues = []
    for p in before:
        replacement = next((q for q in after if q["name"] == p["name"]), None)
        if (
            replacement
            and not p["required"]
            and not replacement["required"]
            and p["default"] != replacement["default"]
        ):
            issues.append(f"default changed for {p['name']}")
    extra_args = any(p.kind == p.VAR_POSITIONAL for p in old.parameters.values())
    extra_kwargs = any(p.kind == p.VAR_KEYWORD for p in old.parameters.values())
    # Probe old accepted positional/keyword/omitted forms. Values identify their
    # original parameter so reordered positional arguments cannot pass silently.
    for modes in itertools.product(("omit", "pos", "kw"), repeat=len(fixed)):
        args, kwargs = [], {}
        for p, mode in zip(fixed, modes, strict=True):
            if mode == "pos":
                args.append(p.name)
            elif mode == "kw":
                kwargs[p.name] = p.name
        for variadic in (False, True) if extra_args or extra_kwargs else (False,):
            call_args, call_kwargs = list(args), dict(kwargs)
            if variadic and extra_args:
                call_args.extend(["extra"] * (len(new.parameters) + 1))
            if variadic and extra_kwargs:
                call_kwargs["__public_api_extra__"] = "extra"
            try:
                accepted = old.bind(*call_args, **call_kwargs)
            except TypeError:
                continue
            try:
                bound = new.bind(*call_args, **call_kwargs)
            except TypeError:
                return [*issues, "a previously accepted call no longer binds"]
            for p in fixed:
                if (
                    p.name in accepted.arguments
                    and p.name in bound.arguments
                    and accepted.arguments[p.name] != bound.arguments[p.name]
                ):
                    return [
                        *issues,
                        "positional arguments bind to different parameters",
                    ]
    return issues


def compare(before, after):
    findings = []
    for name, target in before["imports"].items():
        if name in after["imports"] and after["imports"][name] != target:
            findings.append(f"{name}: documented import path changed")
    for name in sorted(before["callables"].keys() | after["callables"].keys()):
        old, new = before["callables"].get(name), after["callables"].get(name)
        if new is None:
            findings.append(
                f"{name}: documented callable missing or removed from scope"
            )
        elif old is not None:
            findings.extend(f"{name}: {issue}" for issue in signature_issues(old, new))
    for name in sorted(before["attributes"].keys() | after["attributes"].keys()):
        if not after["attributes"].get(name):
            findings.append(
                f"{name}: documented attribute missing or removed from scope"
            )
    for name in sorted(before["constants"].keys() | after["constants"].keys()):
        new = after["constants"].get(name)
        if not new or not new["present"]:
            findings.append(
                f"{name}: documented constant missing or removed from scope"
            )
        elif (
            before["constants"].get(name, {}).get("present")
            and before["constants"][name] != new
        ):
            findings.append(f"{name}: documented constant changed")
    return findings


def capture(root, surface, output):
    try:
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--capture",
                str(root),
                "--surface",
                str(surface),
                "--output",
                str(output),
            ],
            check=True,
            timeout=60,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"API snapshot failed; no compatibility verdict:\n{error.stderr}"
        ) from error
    return json.loads(output.read_text())


def revision_tree(ref, destination):
    sha = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ],
        text=True,
    ).strip()
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", sha])
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination, filter="data")
    return sha


def run_comparison(base, candidate, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.md").write_text(
        "## Public Python API (advisory)\n\n"
        "Comparison incomplete; inspect the command or job logs. No compatibility verdict.\n"
    )
    with TemporaryDirectory(prefix="glance-public-api-") as directory:
        work = Path(directory)
        base_root, candidate_root = work / "base", ROOT
        base_sha = revision_tree(base, base_root)
        candidate_sha = "WORKTREE"
        if candidate != "WORKTREE":
            candidate_root = work / "candidate"
            candidate_sha = revision_tree(candidate, candidate_root)
        inventory = candidate_root / SURFACE
        if not inventory.is_file():
            raise ValueError(
                "Candidate has no public API inventory; select a revision containing Q4"
            )
        baseline_inventory = base_root / SURFACE
        bootstrap = not baseline_inventory.is_file()
        before = capture(
            base_root,
            inventory if bootstrap else baseline_inventory,
            output / "base.json",
        )
        after = capture(candidate_root, inventory, output / "candidate.json")
    findings = compare(before, after)
    lines = [
        "## Public Python API (advisory)",
        "",
        f"Base: `{base_sha}`. Candidate: `{candidate_sha}`.",
        "",
    ]
    if bootstrap:
        lines += [
            "Base predates the inventory; the candidate's documented scope was used for both revisions.",
            "",
        ]
    lines += [
        f"{len(findings)} item(s) need review.",
        "",
        *[f"- {item}" for item in findings],
    ]
    lines += [
        "",
        "This structural comparison does not prove behavioral compatibility. Keep the CLI, policy, reader, prepared-view and URL tests; review intentional changes and upgrade guidance.",
    ]
    text = "\n".join(lines) + "\n"
    (output / "summary.md").write_text(text)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(text)
    return bool(findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Explicit Git baseline revision")
    parser.add_argument(
        "--candidate", default="WORKTREE", help="Git revision or WORKTREE (default)"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Opt-in nonzero exit for controlled acceptance checks",
    )
    parser.add_argument("--capture", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--surface", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.capture:
        sys.path.insert(0, str(args.capture.resolve()))
        surface = tomllib.loads(args.surface.read_text())
        args.output.write_text(
            json.dumps(snapshot(surface, args.capture), indent=2) + "\n"
        )
        return 0
    if not args.base:
        parser.error("--base is required; select an explicit supported baseline")
    changed = run_comparison(args.base, args.candidate, args.output.resolve())
    return int(changed and args.fail_on_change)


if __name__ == "__main__":
    raise SystemExit(main())
