# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Sequential refresh orchestration; completed stages remain available on failure."""

import argparse
import logging
import re
from time import perf_counter

from .citations.store import load_store
from .console import print_summary
from .registry.public_identifiers import default_identifiers_path, load_identifiers
from .views.assets import ASSET_NAMES
from .views.build import render_group
from .views.curation import load_publication_policy
from .views.profiles import GroupProfile

logger = logging.getLogger(__name__)


def prepare_refresh(args):
    """Validate configuration and destinations before requesting authentication."""
    groups = args.groups
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_-]*", group) for group in groups):
        raise ValueError("Groups must be uppercase tokens, e.g. TOPQ or HIGP")
    if len(set(groups)) != len(groups):
        raise ValueError("Each group must be requested only once")
    plans = [
        (
            args.output_dir if len(groups) == 1 else args.output_dir / group.lower(),
            GroupProfile(
                group,
                publication_policy=load_publication_policy(args.curation_config, group),
            ),
        )
        for group in groups
    ]
    protected = [args.curation_config, args.doi_cache, default_identifiers_path()]
    outputs = [args.api_snapshot, args.snapshot]
    names = [
        "ongoing.md",
        "papers.md",
        "confnotes.md",
        "pubnotes.md",
        "view-report.json",
    ]
    names += ["assets/" + name for name in ASSET_NAMES]
    outputs += [directory / name for directory, _ in plans for name in names]
    resolved = [path.resolve() for path in outputs]
    inputs = {path.resolve() for path in protected}
    if len(set(resolved)) != len(resolved) or inputs.intersection(resolved):
        raise ValueError(
            "Refresh destinations must be distinct and must not overwrite configuration or dictionaries"
        )
    for path in resolved:
        if path.is_dir() or any(
            parent in resolved or parent.is_file() for parent in path.parents
        ):
            raise ValueError(
                f"Refresh output conflicts with a directory or parent file: {path}"
            )
    load_store(args.doi_cache)
    load_identifiers(default_identifiers_path())
    return plans


def refresh(args, *, download, build):
    plans = prepare_refresh(args)
    started = perf_counter()
    stage = "API download"
    try:
        logger.info(
            "Refresh 1/3: downloading one shared API snapshot for %s",
            ", ".join(args.groups),
        )
        download(argparse.Namespace(**(vars(args) | {"output": args.api_snapshot})))
        stage = "registry build"
        logger.info("Refresh 2/3: building curated registry")
        build(argparse.Namespace(**(vars(args) | {"output": args.snapshot})))
        results = []
        for directory, profile in plans:
            stage = f"rendering {profile.group}"
            logger.info("Refresh 3/3: rendering %s into %s", profile.group, directory)
            counts = render_group(args.snapshot, directory, profile)
            results.extend(
                [
                    (profile.group, directory),
                    ("Report", directory / "view-report.json"),
                    *[
                        (f"{profile.group} {key}", value)
                        for key, value in counts.items()
                    ],
                ]
            )
    except BaseException:
        logger.error(
            "Refresh stopped during %s; later steps were not run. Completed outputs are retained; no workflow-wide rollback is performed.",
            stage,
        )
        raise
    print_summary(
        "Refresh complete",
        [
            ("API snapshot", args.api_snapshot),
            ("Curated registry", args.snapshot),
            *results,
            ("Elapsed", f"{perf_counter() - started:.2f}s"),
        ],
        color=args.color,
    )
