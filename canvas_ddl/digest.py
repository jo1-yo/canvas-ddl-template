"""Sort the next two weeks into sections and write them out.

Three sections, because they get read differently. What lands in the next few
days is what you act on today. Exams are worth seeing whatever week they fall
in, since they need preparing for rather than submitting. Everything else is
context.

Two renderings: `markdown` for the email, `text` for a push notification, which
has no formatting and very little room.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .ics import Deadline

WINDOW_DAYS = 14
SOON_DAYS = 7
COURSE_MAX_CHARS = 44

SUBJECT = "\U0001F4DA Your Canvas deadlines & exams — next 2 weeks"

# Nothing in a Canvas feed marks an exam, so go by what it is called. Users can
# replace this through EXAM_TITLES.
DEFAULT_EXAM_PATTERN = r"\b(exam|midterm|final|finals|quiz|test)\b"

PAWSE_URL = "https://chromewebstore.google.com/detail/nfmdjdfakglljjpefcbbcjfapgiohoec?utm_source=item-share-cb"

# Canvas course names arrive as registrar strings that are unreadable in a
# notification: "COGSUN3951_001_2026_3 - Computational Models of Decision-Making"
# or "Fall 2026 First Year Japanese I (Section 002)".
_COURSE_CODE = re.compile(r"^[A-Z]{2,8}[A-Z0-9]*[_\-][A-Z0-9_\-]+\s+-\s+", re.IGNORECASE)
_TERM_PREFIX = re.compile(r"^(spring|summer|fall|autumn|winter)\s+\d{4}\s+", re.IGNORECASE)
_SECTION_SUFFIX = re.compile(r"\s*\((section|sec)\.?\s*[\w-]+\)\s*$", re.IGNORECASE)
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>])")


@dataclass(frozen=True)
class Digest:
    soon: list[Deadline]
    exams: list[Deadline]
    later: list[Deadline]
    now: dt.datetime

    title = SUBJECT

    @property
    def is_empty(self) -> bool:
        return not (self.soon or self.exams or self.later)

    @property
    def summary(self) -> str:
        if self.is_empty:
            return "Nothing due in the next two weeks. Enjoy it."
        parts = []
        work = len(self.soon) + len(self.later)
        if work:
            parts.append(f"{work} {_plural(work, 'assignment')}")
        if self.exams:
            parts.append(f"{len(self.exams)} {_plural(len(self.exams), 'exam')}")
        return f"You have {' and '.join(parts)} coming up in the next two weeks."

    @property
    def markdown(self) -> str:
        blocks = ["Hi!", "", "Here's your schoolwork from Canvas for the next two weeks."]

        for heading, items, kind in (
            ("\U0001F534 Coming Up Soon", self.soon, "due"),
            ("\U0001F4DD Exams", self.exams, "exam"),
            ("\U0001F4C5 Coming Up Later", self.later, "due"),
        ):
            if not items:
                continue
            blocks += ["", f"## {heading}"]
            for day, entries in _by_day(items):
                blocks += ["", f"**{_date_label(day)}**", ""]
                for entry in entries:
                    blocks.append(f"- {_line_one(entry, markdown=True)}")
                    blocks.append(f"- {_line_two(entry, kind)}")

        blocks += [
            "",
            "---",
            "",
            f"\U0001F4A1 **Quick Summary:** {self.summary} "
            f"Use [pawse]({PAWSE_URL}) to manage your time more effectively.",
        ]
        return "\n".join(blocks)

    @property
    def text(self) -> str:
        """Plain text, for a push notification: no greeting, no sign-off."""
        if self.is_empty:
            return "Nothing due in the next two weeks."

        lines: list[str] = []
        for heading, items, kind in (
            ("Coming Up Soon", self.soon, "due"),
            ("Exams", self.exams, "exam"),
            ("Coming Up Later", self.later, "due"),
        ):
            if not items:
                continue
            if lines:
                lines.append("")
            lines.append(heading)
            for day, entries in _by_day(items):
                lines.append(f"  {_date_label(day)}")
                for entry in entries:
                    lines.append(f"    {_line_one(entry, markdown=False)}")
                    lines.append(f"    {_line_two(entry, kind)}")
        return "\n".join(lines)


def select(
    deadlines: list[Deadline],
    now: dt.datetime,
    *,
    window_days: int = WINDOW_DAYS,
    soon_days: int = SOON_DAYS,
    exam_pattern: str = DEFAULT_EXAM_PATTERN,
) -> Digest:
    """Split the window into what is soon, what is an exam, and what is later."""
    window_end = _end_of_day(now + dt.timedelta(days=window_days - 1))
    soon_end = _end_of_day(now + dt.timedelta(days=soon_days - 1))
    upcoming = [d for d in deadlines if now <= d.due <= window_end]

    try:
        is_exam = re.compile(exam_pattern, re.IGNORECASE).search
    except re.error:
        is_exam = re.compile(DEFAULT_EXAM_PATTERN, re.IGNORECASE).search

    soon: list[Deadline] = []
    exams: list[Deadline] = []
    later: list[Deadline] = []
    for item in upcoming:
        if is_exam(item.title):
            exams.append(item)
        elif item.due <= soon_end:
            soon.append(item)
        else:
            later.append(item)

    return Digest(soon=soon, exams=exams, later=later, now=now)


def _line_one(item: Deadline, *, markdown: bool) -> str:
    """`Math 101 — Problem Set 3`, with the title linked in the email."""
    title = _escape(item.title) if markdown else item.title
    if markdown and item.url:
        title = f"[{title}]({item.url})"
    if not item.course:
        return title
    course = shorten_course(item.course)
    return f"{_escape(course) if markdown else course} — {title}"


def _line_two(item: Deadline, kind: str) -> str:
    """`Due at 11:59 PM` for work, a bare time for an exam."""
    if item.all_day:
        return "Due by end of day" if kind == "due" else "All day"
    when = _time_label(item)
    return f"Due at {when}" if kind == "due" else when


def _plural(count: int, word: str) -> str:
    return word if count == 1 else word + "s"


def _by_day(items: list[Deadline]) -> list[tuple[dt.date, list[Deadline]]]:
    grouped: dict[dt.date, list[Deadline]] = {}
    for item in sorted(items, key=lambda d: d.due):
        grouped.setdefault(item.due.date(), []).append(item)
    return sorted(grouped.items())


def _end_of_day(moment: dt.datetime) -> dt.datetime:
    return moment.replace(hour=23, minute=59, second=59, microsecond=999999)


def _date_label(day: dt.date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def _time_label(item: Deadline) -> str:
    hour = item.due.hour % 12 or 12
    meridiem = "AM" if item.due.hour < 12 else "PM"
    return f"{hour}:{item.due.strftime('%M')} {meridiem}"


def _escape(value: str) -> str:
    """Keep a title with brackets or asterisks from breaking the Markdown."""
    return _MD_SPECIAL.sub(r"\\\1", value)


def shorten_course(course: str) -> str:
    """Trim a registrar course name down to something readable."""
    name = _COURSE_CODE.sub("", course.strip())
    name = _TERM_PREFIX.sub("", name)
    name = _SECTION_SUFFIX.sub("", name).strip()
    if not name:
        name = course.strip()
    if len(name) > COURSE_MAX_CHARS:
        name = name[: COURSE_MAX_CHARS - 1].rstrip() + "…"
    return name
