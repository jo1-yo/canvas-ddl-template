"""Entry point: fetch the Canvas feed, build a digest, deliver it.

    python -m canvas_ddl
    python -m canvas_ddl --dry-run

Configuration comes from the environment:

    CANVAS_ICS_URL   required   the secret .ics link from Canvas
    CHANNEL          optional   issue | bark, default issue
    TIMEZONE         optional   IANA name, default America/Los_Angeles
    WINDOW_DAYS      optional   how far ahead to look, default 14
    SOON_DAYS        optional   where "Coming Up Soon" ends, default 7
    EXAM_TITLES      optional   regular expression that marks an exam;
                                default matches exam/midterm/final/quiz/test
    INCLUDE_EVENTS   optional   "1" to also list class meetings and office
                                hours, which are on the calendar but are not
                                things you submit. Default: assignments only.
    IGNORE_TITLES    optional   one regular expression per line; any entry
                                whose title matches is left out. Instructors
                                often file class sessions as assignments, and
                                only you can say which titles those are.

    CHANNEL=issue    GITHUB_TOKEN and GITHUB_REPOSITORY, both provided
                     automatically inside GitHub Actions
    CHANNEL=bark     BARK_KEY required; BARK_SERVER optional
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import bark, github_issue
from .digest import DEFAULT_EXAM_PATTERN, select
from .ics import Deadline, FeedError, fetch, parse

DEFAULT_TIMEZONE = "America/Los_Angeles"
CHANNELS = ("issue", "bark")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="canvas_ddl", description=__doc__)
    parser.add_argument("--channel", choices=CHANNELS, default=os.environ.get("CHANNEL", "issue"))
    parser.add_argument(
        "--include-events",
        action="store_true",
        default=os.environ.get("INCLUDE_EVENTS", "").strip() in {"1", "true", "yes"},
        help="also list calendar entries that are not submittable work",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the digest instead of delivering it")
    args = parser.parse_args(argv)

    feed_url = os.environ.get("CANVAS_ICS_URL", "").strip()
    if not feed_url:
        _fail("CANVAS_ICS_URL is not set.")
        return 2

    tz_name = os.environ.get("TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        _fail(f"TIMEZONE {tz_name!r} is not a valid IANA timezone.")
        return 2

    try:
        deadlines = parse(fetch(feed_url), tz)
    except FeedError as exc:
        # exc never contains the feed URL — see ics.fetch.
        _fail(f"Could not read the Canvas feed: {exc}")
        return 1

    total = len(deadlines)
    if not args.include_events:
        deadlines = [d for d in deadlines if d.is_assignment]
    dropped_kind = total - len(deadlines)

    deadlines, dropped_title = apply_ignore_list(deadlines, os.environ.get("IGNORE_TITLES", ""))

    now = dt.datetime.now(tz)
    digest = select(
        deadlines,
        now,
        window_days=_positive_int("WINDOW_DAYS", 14),
        soon_days=_positive_int("SOON_DAYS", 7),
        exam_pattern=os.environ.get("EXAM_TITLES", "").strip() or DEFAULT_EXAM_PATTERN,
    )
    shown = digest.soon + digest.exams + digest.later

    skipped = []
    if dropped_kind:
        skipped.append(f"{dropped_kind} not submittable")
    if dropped_title:
        skipped.append(f"{dropped_title} ignored by title")
    _say(
        f"{total} entries in feed"
        + (f" ({', '.join(skipped)})" if skipped else "")
        + f", {len(digest.soon)} soon, {len(digest.exams)} exams,"
        f" {len(digest.later)} later."
    )

    if args.dry_run:
        _say(f"\n=== {digest.title} ===\n\n{digest.markdown}")
        return 0

    try:
        _deliver(args.channel, digest, shown)
    except (bark.PushError, github_issue.IssueError) as exc:
        _fail(f"Delivery failed ({args.channel}): {exc}")
        return 1
    return 0


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        _fail(f"{name}={raw!r} is not a number; using {default}.")
        return default
    if value < 1:
        _fail(f"{name} must be at least 1; using {default}.")
        return default
    return value


def apply_ignore_list(deadlines: list[Deadline], raw: str) -> tuple[list[Deadline], int]:
    """Drop entries whose title matches any pattern. Returns (kept, dropped).

    A bad pattern is reported and skipped rather than failing the run: losing
    one filter is better than losing the whole digest.
    """
    patterns = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            patterns.append(re.compile(line, re.IGNORECASE))
        except re.error as exc:
            _fail(f"Ignoring bad IGNORE_TITLES pattern {line!r}: {exc}")

    if not patterns:
        return deadlines, 0

    kept = [d for d in deadlines if not any(p.search(d.title) for p in patterns)]
    return kept, len(deadlines) - len(kept)


def _deliver(channel: str, digest, shown) -> None:
    if channel == "bark":
        key = os.environ.get("BARK_KEY", "").strip()
        if not key:
            raise bark.PushError("BARK_KEY is not set")
        if key.startswith("http"):
            raise bark.PushError(
                "BARK_KEY looks like a full URL. Store only the key segment, "
                "e.g. AbCdEf123456 from https://api.day.app/AbCdEf123456/"
            )
        server = os.environ.get("BARK_SERVER", bark.DEFAULT_SERVER).strip() or bark.DEFAULT_SERVER
        link = shown[0].url if shown and shown[0].url else None
        bark.send(key, digest.title, digest.text, url=link, server=server)
        _say("Pushed to Bark.")
        return

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    owner = repository.split("/")[0] if "/" in repository else None
    url = github_issue.send(
        os.environ.get("GITHUB_TOKEN", "").strip(),
        repository,
        digest.title,
        digest.markdown,
        assignee=owner,
    )
    _say(f"Opened issue: {url}")


def _say(message: str) -> None:
    print(message, flush=True)


def _fail(message: str) -> None:
    sys.stdout.flush()  # keep stdout and stderr in order in CI logs
    print(message, file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
