"""Fetch and parse a Canvas ICS calendar feed into deadlines.

The feed URL is a bearer secret: anyone holding it can read the calendar.
Nothing in this module may put it into a log, an exception message, or a
traceback — see `fetch`.
"""

from __future__ import annotations

import datetime as dt
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from icalendar import Calendar

FETCH_TIMEOUT_S = 20
MAX_FEED_BYTES = 5 * 1024 * 1024
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_S = (2, 5)
USER_AGENT = "canvas-ddl/1.0"

# Canvas names assignments "Lab 7 [CS61A Fall 2026]" — course in trailing brackets.
_COURSE_RE = re.compile(r"^(?P<title>.*?)\s*\[(?P<course>[^\[\]]+)\]\s*$")

# Canvas marks submittable work apart from ordinary calendar entries. An
# assignment links to /assignments/<id> and its UID starts with
# "event-assignment-"; a class meeting or office hour links to
# /calendar_events/<id>. Quizzes and graded discussions are submittable too.
SUBMITTABLE_PATHS = ("/assignments/", "/quizzes/", "/discussion_topics/")
_SUBMITTABLE_UID = re.compile(r"^event-(assignment|quiz|discussion)", re.IGNORECASE)

KIND_ASSIGNMENT = "assignment"
KIND_EVENT = "event"

# Canvas points the URL at the calendar with an anchor rather than at the
# assignment itself:
#   .../calendar?include_contexts=course_1234&month=09#assignment_5678
# Both ids are right there, so rebuild the direct link and land on the page
# with the instructions instead of a month grid.
_CALENDAR_LINK = re.compile(
    r"^(?P<root>https://[^/]+)/calendar\?[^#]*include_contexts=course_(?P<course>\d+)"
    r"[^#]*#(?P<kind>assignment|event)_(?P<id>\d+)$",
    re.IGNORECASE,
)


class FeedError(RuntimeError):
    """Feed could not be fetched or parsed. Never carries the feed URL."""


@dataclass(frozen=True)
class Deadline:
    title: str
    course: str | None
    due: dt.datetime  # timezone-aware, in the caller's timezone
    url: str | None
    all_day: bool
    kind: str = KIND_ASSIGNMENT

    @property
    def is_assignment(self) -> bool:
        return self.kind == KIND_ASSIGNMENT


def fetch(url: str) -> bytes:
    """GET the feed, retrying transient failures.

    Raises FeedError with the URL stripped from the message.
    """
    if not url.startswith("https://"):
        raise FeedError("feed URL must start with https://")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: FeedError | None = None

    for attempt in range(FETCH_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
                raw = response.read(MAX_FEED_BYTES + 1)
        except urllib.error.HTTPError as exc:
            # str(exc) is safe, but exc.url / exc.filename are not.
            last_error = FeedError(f"Canvas returned HTTP {exc.code}")
            if exc.code < 500:
                raise last_error from None  # 401/404 will not fix themselves
        except urllib.error.URLError as exc:
            last_error = FeedError(f"could not reach Canvas: {exc.reason}")
        except OSError as exc:
            last_error = FeedError(f"network error: {exc.strerror or 'unknown'}")
        else:
            if len(raw) > MAX_FEED_BYTES:
                raise FeedError("feed is larger than 5 MB — refusing to parse")
            if b"BEGIN:VCALENDAR" not in raw[:2048]:
                raise FeedError("response is not an iCalendar feed (is the link still valid?)")
            return raw

        if attempt < FETCH_ATTEMPTS - 1:
            time.sleep(FETCH_BACKOFF_S[attempt])

    raise last_error or FeedError("could not read the feed")


def parse(raw: bytes, tz: ZoneInfo) -> list[Deadline]:
    """Parse feed bytes into deadlines, with times converted to `tz`.

    Recurring entries (anything with an RRULE) are dropped: on a Canvas feed
    those are weekly class meetings, which are not deadlines and would
    otherwise flood every digest. Non-recurring calendar entries are kept but
    tagged KIND_EVENT so the caller can decide.
    """
    try:
        calendar = Calendar.from_ical(raw)
    except Exception as exc:  # icalendar raises bare ValueError subclasses
        raise FeedError(f"could not parse the feed: {exc}") from None

    deadlines: list[Deadline] = []
    for component in calendar.walk("VEVENT"):
        if component.get("RRULE") is not None:
            continue

        start = component.get("DTSTART")
        if start is None:
            continue
        due, all_day = _localize(start.dt, tz)
        if due is None:
            continue

        summary = str(component.get("SUMMARY") or "").strip()
        if not summary:
            continue
        title, course = _split_course(summary)

        url_value = component.get("URL")
        url = direct_link(str(url_value)) if url_value else None
        deadlines.append(
            Deadline(
                title=title,
                course=course,
                due=due,
                url=url,
                all_day=all_day,
                kind=_classify(url, str(component.get("UID") or "")),
            )
        )

    deadlines.sort(key=lambda d: d.due)
    return deadlines


def direct_link(url: str) -> str:
    """Turn a Canvas calendar-anchor URL into a link to the assignment page.

    Anything that does not match is returned unchanged.
    """
    match = _CALENDAR_LINK.match(url.strip())
    if not match:
        return url
    if match.group("kind").lower() != "assignment":
        return url
    return (
        f"{match.group('root')}/courses/{match.group('course')}"
        f"/assignments/{match.group('id')}"
    )


def _classify(url: str | None, uid: str) -> str:
    if url and any(path in url for path in SUBMITTABLE_PATHS):
        return KIND_ASSIGNMENT
    if _SUBMITTABLE_UID.match(uid):
        return KIND_ASSIGNMENT
    return KIND_EVENT


def _localize(value: object, tz: ZoneInfo) -> tuple[dt.datetime | None, bool]:
    """Convert a DTSTART value into an aware datetime in `tz`.

    An all-day entry has no time of day; Canvas means "that day", so it is
    pinned to 23:59 local rather than midnight, which would sort it before
    everything else due that same day.
    """
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(tz), False
    if isinstance(value, dt.date):
        end_of_day = dt.datetime.combine(value, dt.time(23, 59), tzinfo=tz)
        return end_of_day, True
    return None, False


def _split_course(summary: str) -> tuple[str, str | None]:
    match = _COURSE_RE.match(summary)
    if not match:
        return summary, None
    title = match.group("title").strip()
    course = match.group("course").strip()
    if not title:  # summary was only "[Course]" — keep it whole
        return summary, None
    return title, course
