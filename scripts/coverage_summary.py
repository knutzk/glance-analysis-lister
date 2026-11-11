# SPDX-FileCopyrightText: 2024-2026 Knut Zoch
# SPDX-License-Identifier: GPL-3.0-only

"""Publish coverage metadata without trusting or executing PR-provided code."""

import argparse
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MARKER = "<!-- glance-python-coverage -->"
LIMIT = 20 * 1024 * 1024


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https":
            raise ValueError("Artifact redirect must use HTTPS")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        # Artifact downloads redirect to storage; never send the API token there.
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, repository, token):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise ValueError("Invalid repository name")
        self.repository = repository
        self.api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
        self.web = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        self.token = token

    def request(self, path, *, method="GET", body=None, binary=False):
        request = Request(
            f"{self.api}/repos/{self.repository}/{path}",
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with build_opener(SafeRedirect()).open(request, timeout=30) as response:
            data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("GitHub response exceeds size limit")
        return data if binary else json.loads(data)

    def pages(self, path, key=None):
        separator = "&" if "?" in path else "?"
        for page in range(1, 101):
            result = self.request(f"{path}{separator}per_page=100&page={page}")
            items = result if key is None else result[key]
            yield from items
            if len(items) < 100:
                return
        raise ValueError("GitHub pagination limit exceeded")


@dataclass(frozen=True)
class Totals:
    lines: tuple[int, int]
    branches: tuple[int, int]


def read_totals(archive):
    """Read only coverage.json, without extracting files or trusting percentages."""
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        entries = [
            entry for entry in zipped.infolist() if entry.filename == "coverage.json"
        ]
        if len(entries) != 1 or entries[0].file_size > LIMIT:
            raise ValueError("Missing, duplicate or oversized coverage.json")
        report = json.loads(zipped.read(entries[0]))
    if (
        not isinstance(report, dict)
        or not isinstance(report.get("meta"), dict)
        or report["meta"].get("branch_coverage") is not True
        or not isinstance(report.get("totals"), dict)
    ):
        raise ValueError("Report does not include branch coverage")
    totals = report["totals"]
    values = []
    for covered_key, total_key in [
        ("covered_lines", "num_statements"),
        ("covered_branches", "num_branches"),
    ]:
        covered, total = totals[covered_key], totals[total_key]
        if (
            type(covered) is not int
            or type(total) is not int
            or not 0 <= covered <= total <= 10**9
        ):
            raise ValueError("Invalid coverage counts")
        values.append((covered, total))
    return Totals(*values)


def coverage(api, run):
    artifacts = list(api.pages(f"actions/runs/{run['id']}/artifacts", "artifacts"))
    artifacts = [
        a for a in artifacts if a["name"] == "python-coverage" and not a["expired"]
    ]
    if len(artifacts) != 1:
        return None, None
    artifact_id = int(artifacts[0]["id"])
    link = (
        f"{api.web}/{api.repository}/actions/runs/{run['id']}/artifacts/{artifact_id}"
    )
    try:
        totals = read_totals(
            api.request(f"actions/artifacts/{artifact_id}/zip", binary=True)
        )
    except HTTPError as error:
        if error.code not in (404, 410):
            raise
        return None, None
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile):
        return None, link
    return totals, link


def complete_tests(api, run):
    jobs = api.pages(
        f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs"
    )
    checks = [job for job in jobs if job["name"] == "checks"]
    if len(checks) != 1:
        return False
    steps = {step["name"]: step.get("conclusion") for step in checks[0]["steps"]}
    return all(
        steps.get(name) == "success"
        for name in ("Run offline regression tests", "Report offline Python coverage")
    )


def percentage(pair):
    covered, total = pair
    return covered / total * 100 if total else None


def cell(pair):
    value = percentage(pair)
    return f"{value:.2f}% ({pair[0]}/{pair[1]})" if value is not None else "N/A (0/0)"


def render(api, run, base_sha, current, baseline, full, report_link, baseline_run):
    url = f"{api.web}/{api.repository}"
    status = "Complete" if full and current else "Incomplete / unavailable"
    text = [
        MARKER,
        "### Python coverage",
        "",
        f"{status} report for PR head `{run['head_sha'][:12]}` "
        f"([CI run]({url}/actions/runs/{run['id']}), attempt {run['run_attempt']}).",
        "PR CI measures the merge with its base, including child Python processes.",
        "",
        "| Measure | PR | Main | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, field in [("Lines", "lines"), ("Branches", "branches")]:
        pr_pair = getattr(current, field) if current else None
        base_pair = getattr(baseline, field) if baseline else None
        delta = "N/A"
        if full and pr_pair and base_pair:
            pr_value, base_value = percentage(pr_pair), percentage(base_pair)
            if pr_value is not None and base_value is not None:
                delta = f"{pr_value - base_value:+.2f} pp"
        text.append(
            f"| {name} | {cell(pr_pair) if pr_pair else 'N/A'} | "
            f"{cell(base_pair) if base_pair else 'N/A'} | {delta} |"
        )
    text.extend(["", "Changes are percentage points (pp), not relative percentages."])
    if baseline:
        text.append(
            f"Main baseline: [`{base_sha[:12]}`]({url}/commit/{base_sha}) "
            f"([successful CI]({url}/actions/runs/{baseline_run['id']}))."
        )
    else:
        text.append(
            f"No usable successful main report for `{base_sha[:12]}`; "
            "comparison is unavailable. No older baseline was substituted."
        )
    if not full or not current:
        text.append(
            "Tests/report generation did not complete successfully, or the artifact is "
            "missing/expired/invalid. Available totals may be partial; no change is calculated."
        )
    if report_link:
        text.append(
            f"[Download full report]({report_link}) (HTML, XML and JSON; "
            "extract and open `html/index.html`; retained for 14 days)."
        )
    text.extend(
        [
            "",
            "Scope: maintained Python package only. Excludes experimental Events, browser "
            "JavaScript, browser/site checks and live CERN access. No coverage gate is enforced.",
        ]
    )
    return "\n".join(text) + "\n"


def matches_pr(pr, run, repository):
    return (
        pr["state"] == "open"
        and pr["head"]["sha"] == run["head_sha"]
        and pr["head"]["ref"] == run["head_branch"]
        and pr["head"]["repo"] is not None
        and pr["head"]["repo"]["id"] == run["head_repository"]["id"]
        and pr["base"]["repo"]["full_name"] == repository
        and pr["base"]["ref"] == "main"
    )


def publish(api, run_id, *, dry_run=False):
    workflow = api.request("actions/workflows/ci.yml")
    run = api.request(f"actions/runs/{run_id}")
    if (
        run["workflow_id"] != workflow["id"]
        or run["event"] != "pull_request"
        or run["status"] != "completed"
        or run["repository"]["full_name"] != api.repository
    ):
        return "Skipped: not a completed PR CI run in this repository."
    sha = run["head_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid run SHA")
    # workflow_run.pull_requests can be empty. Query by fork owner and branch
    # rather than relying on commit associations being visible in the base repo.
    query = urlencode(
        {
            "state": "open",
            "base": "main",
            "head": f"{run['head_repository']['owner']['login']}:{run['head_branch']}",
        }
    )
    candidates = list(api.pages(f"pulls?{query}"))
    candidates = [pr for pr in candidates if matches_pr(pr, run, api.repository)]
    if len(candidates) != 1:
        return "Skipped: no unique open PR matching the run head and repository."
    pr = api.request(f"pulls/{candidates[0]['number']}")
    if not matches_pr(pr, run, api.repository):
        return "Skipped: PR changed before preparing coverage."
    query = urlencode({"event": "pull_request", "head_sha": sha})
    latest = list(
        api.pages(f"actions/workflows/{workflow['id']}/runs?{query}", "workflow_runs")
    )
    if any(
        (r["id"], r["run_attempt"]) > (run["id"], run["run_attempt"]) for r in latest
    ):
        return "Skipped: a newer PR CI run or attempt exists."

    base_sha = pr["base"]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ValueError("Invalid main SHA")
    query = urlencode(
        {"event": "push", "branch": "main", "head_sha": base_sha, "status": "success"}
    )
    baselines = list(
        api.pages(f"actions/workflows/{workflow['id']}/runs?{query}", "workflow_runs")
    )
    baselines = [
        r
        for r in baselines
        if r["head_sha"] == base_sha
        and r["head_branch"] == "main"
        and r["event"] == "push"
        and r["conclusion"] == "success"
    ]
    baseline_run = max(
        baselines, key=lambda r: (r["id"], r["run_attempt"]), default=None
    )
    baseline = None
    if baseline_run and complete_tests(api, baseline_run):
        baseline, _ = coverage(api, baseline_run)
    current, report_link = coverage(api, run)
    body = render(
        api,
        run,
        base_sha,
        current,
        baseline,
        complete_tests(api, run),
        report_link,
        baseline_run,
    )
    # Recheck after downloads: do not attach an old result to a new PR revision.
    fresh = api.request(f"pulls/{pr['number']}")
    if not matches_pr(fresh, run, api.repository) or fresh["base"]["sha"] != base_sha:
        return "Skipped: PR changed while preparing coverage."
    if dry_run:
        return body
    comments = api.pages(f"issues/{pr['number']}/comments")
    owned = [
        comment
        for comment in comments
        if comment["user"]["login"] == "github-actions[bot]"
        and comment["user"]["type"] == "Bot"
        and comment.get("body", "").startswith(MARKER)
    ]
    if owned:
        api.request(
            f"issues/comments/{owned[0]['id']}", method="PATCH", body={"body": body}
        )
    else:
        api.request(
            f"issues/{pr['number']}/comments", method="POST", body={"body": body}
        )
    return f"Updated coverage summary for PR #{pr['number']}."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the comment without writing to GitHub",
    )
    args = parser.parse_args()
    print(
        publish(
            GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]),
            args.run_id,
            dry_run=args.dry_run,
        )
    )
