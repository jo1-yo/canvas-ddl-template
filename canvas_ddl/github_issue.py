"""Post the digest as a GitHub issue, assigned to you.

Needs no new account, no new app and no new secret: inside GitHub Actions
both GITHUB_TOKEN and GITHUB_REPOSITORY are provided automatically. GitHub
emails you when an issue is assigned to you, and pushes it if you have the
GitHub mobile app.

The workflow must grant `permissions: issues: write`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

API_ROOT = "https://api.github.com"
TIMEOUT_S = 15


class IssueError(RuntimeError):
    """The issue could not be created. Never carries the token."""


def send(
    token: str,
    repository: str,
    title: str,
    body: str,
    *,
    assignee: str | None = None,
    label: str = "canvas-ddl",
) -> str:
    """Create the issue and return its html_url."""
    if not token:
        raise IssueError("GITHUB_TOKEN is empty")
    if "/" not in repository:
        raise IssueError(f"GITHUB_REPOSITORY should look like owner/repo, got {repository!r}")

    payload: dict[str, object] = {
        "title": title,
        "body": body,
        "labels": [label],
    }
    if assignee:
        payload["assignees"] = [assignee]

    request = urllib.request.Request(
        f"{API_ROOT}/repos/{repository}/issues",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "canvas-ddl",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            result = json.loads(response.read(8192))
    except urllib.error.HTTPError as exc:
        hint = {
            401: "the token was rejected",
            403: "the workflow needs `permissions: issues: write`",
            404: "repository not found, or the token cannot see it",
            410: "issues are disabled for this repository",
        }.get(exc.code, "unexpected response")
        raise IssueError(f"GitHub returned HTTP {exc.code} — {hint}") from None
    except urllib.error.URLError as exc:
        raise IssueError(f"could not reach GitHub: {exc.reason}") from None

    new_number = result.get("number")
    # Close last week's digest only after this one exists, so there is never a
    # moment with nothing open.
    close_previous(token, repository, label=label, keep=new_number)
    return str(result.get("html_url", ""))


def close_previous(token: str, repository: str, *, label: str, keep: int | None) -> int:
    """Close open digests from earlier runs. Returns how many were closed.

    Never raises: a stale issue left open is not worth failing the run over.
    """
    closed = 0
    try:
        listing = _api(
            token,
            "GET",
            f"/repos/{repository}/issues?state=open&labels={label}&per_page=100",
        )
    except IssueError:
        return 0

    for issue in listing if isinstance(listing, list) else []:
        number = issue.get("number")
        if number is None or number == keep or "pull_request" in issue:
            continue
        try:
            _api(
                token,
                "PATCH",
                f"/repos/{repository}/issues/{number}",
                {"state": "closed", "state_reason": "completed"},
            )
            closed += 1
        except IssueError:
            continue
    return closed


def _api(token: str, method: str, path: str, payload: dict | None = None):
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "canvas-ddl",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read(1 << 20) or b"null")
    except urllib.error.HTTPError as exc:
        raise IssueError(f"GitHub returned HTTP {exc.code} for {method} {path}") from None
    except urllib.error.URLError as exc:
        raise IssueError(f"could not reach GitHub: {exc.reason}") from None
