import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from canvas_ddl.digest import SUBJECT, select, shorten_course
from canvas_ddl.ics import Deadline, parse

FIXTURE = Path(__file__).parent / "fixtures" / "canvas_sample.ics"
LA = ZoneInfo("America/Los_Angeles")

# Monday 2026-09-21, 08:00 local. Lab 7 is due 23:59 the same evening.
NOW = dt.datetime(2026, 9, 21, 8, 0, tzinfo=LA)


@pytest.fixture
def deadlines():
    return parse(FIXTURE.read_bytes(), LA)


def _at(days, hour=12, minute=0, title="Homework 1", course=None, all_day=False):
    due = (NOW + dt.timedelta(days=days)).replace(hour=hour, minute=minute)
    return Deadline(title=title, course=course, due=due, url=None, all_day=all_day)


# --- sectioning -------------------------------------------------------------

def test_the_window_is_two_weeks():
    digest = select([_at(3), _at(10), _at(20)], NOW)
    assert len(digest.soon) == 1
    assert len(digest.later) == 1  # the day-20 item is outside the window


def test_soon_and_later_split_at_one_week():
    """soon_days=7 counts today plus six more, so day 7 has fallen out."""
    digest = select([_at(1), _at(6), _at(7), _at(13)], NOW)
    assert len(digest.soon) == 2
    assert len(digest.later) == 2


def test_past_deadlines_are_excluded():
    digest = select([_at(-1), _at(2)], NOW)
    assert len(digest.soon) == 1


def test_exams_are_pulled_out_of_both_sections():
    digest = select(
        [
            _at(2, title="Problem Set 3"),
            _at(3, title="CS 201 Midterm"),
            _at(10, title="Final Exam"),
            _at(11, title="Essay"),
        ],
        NOW,
    )
    assert [d.title for d in digest.soon] == ["Problem Set 3"]
    assert [d.title for d in digest.exams] == ["CS 201 Midterm", "Final Exam"]
    assert [d.title for d in digest.later] == ["Essay"]


@pytest.mark.parametrize(
    "title, is_exam",
    [
        ("Midterm 1", True),
        ("Final Exam", True),
        ("Quiz 2", True),
        ("Unit Test 3", True),
        ("Class 5 Pre-Quiz: JavaScript Lab", True),
        ("Problem Set 3", False),
        ("Reading Response", False),
        ("Testing Frameworks Essay", False),  # "Testing" must not match "test"
    ],
)
def test_what_counts_as_an_exam(title, is_exam):
    digest = select([_at(2, title=title)], NOW)
    assert bool(digest.exams) is is_exam


def test_a_bad_exam_pattern_falls_back_to_the_default():
    digest = select([_at(2, title="Midterm")], NOW, exam_pattern="[unclosed")
    assert len(digest.exams) == 1


# --- the email --------------------------------------------------------------

def test_subject_is_fixed():
    assert select([], NOW).title == SUBJECT
    assert SUBJECT == "\U0001F4DA Your Canvas deadlines & exams — next 2 weeks"


def test_email_follows_the_agreed_layout():
    digest = select(
        [
            _at(5, hour=23, minute=59, title="Problem Set 3", course="Math 101"),
            _at(9, hour=10, minute=0, title="Midterm", course="CS 201"),
            _at(12, hour=23, minute=59, title="Essay", course="English"),
        ],
        NOW,
    )
    md = digest.markdown

    assert md.startswith("Hi!")
    assert "Here's your schoolwork from Canvas for the next two weeks." in md
    assert "## \U0001F534 Coming Up Soon" in md
    assert "## \U0001F4DD Exams" in md
    assert "## \U0001F4C5 Coming Up Later" in md
    assert "**Sep 26**" in md
    assert "- Math 101 — Problem Set 3" in md
    assert "- Due at 11:59 PM" in md
    # an exam shows a bare time, not "Due at"
    assert "- CS 201 — Midterm" in md
    assert "- 10:00 AM" in md


def test_empty_sections_are_left_out():
    md = select([_at(2, title="Problem Set 3")], NOW).markdown
    assert "Coming Up Soon" in md
    assert "Exams" not in md
    assert "Coming Up Later" not in md


def test_quick_summary_counts_and_pluralises():
    digest = select(
        [_at(2), _at(3), _at(11), _at(4, title="Midterm"), _at(5, title="Quiz 2")],
        NOW,
    )
    assert digest.summary == "You have 3 assignments and 2 exams coming up in the next two weeks."
    assert "\U0001F4A1 **Quick Summary:**" in digest.markdown


def test_summary_with_one_of_each():
    digest = select([_at(2), _at(3, title="Final Exam")], NOW)
    assert digest.summary == "You have 1 assignment and 1 exam coming up in the next two weeks."


def test_summary_with_only_exams():
    digest = select([_at(3, title="Final Exam")], NOW)
    assert digest.summary == "You have 1 exam coming up in the next two weeks."


def test_an_empty_two_weeks_still_says_something():
    digest = select([], NOW)
    assert digest.is_empty
    assert digest.summary == "Nothing due in the next two weeks. Enjoy it."
    assert "Nothing due" in digest.markdown
    assert "Nothing due" in digest.text


def test_pawse_is_linked_by_name():
    md = select([_at(2)], NOW).markdown
    assert "[pawse](https://chromewebstore.google.com/detail/" in md
    assert "to manage your time more effectively." in md


def test_titles_link_to_canvas(deadlines):
    md = select(deadlines, NOW).markdown
    assert "[Lab 7: Scheme Interpreter](https://example.instructure.com/courses/1/assignments/11111)" in md
    assert "```" not in md


def test_all_day_items_say_end_of_day():
    md = select([_at(2, title="Hiragana #7-8", all_day=True)], NOW).markdown
    assert "- Due by end of day" in md


def test_markdown_escapes_characters_that_would_break_formatting():
    md = select([_at(2, title="Read *chapter* [2]")], NOW).markdown
    assert r"Read \*chapter\* \[2\]" in md


# --- push notification ------------------------------------------------------

def test_push_text_drops_the_greeting_and_sign_off():
    text = select([_at(2, title="Problem Set 3", course="Math 101")], NOW).text
    assert "Hi!" not in text
    assert "pawse" not in text
    assert "Coming Up Soon" in text
    assert "Math 101 — Problem Set 3" in text
    assert "[" not in text  # no Markdown links in a push


# --- course names -----------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            "COGSUN3951_001_2026_3 - Computational Models of Decision-Making",
            "Computational Models of Decision-Making",
        ),
        ("COMSW4170_001_2026_3 - USER INTERFACE DESIGN", "USER INTERFACE DESIGN"),
        ("COMSW3134_002_2026_3 - DATA STRUCTURES IN JAVA", "DATA STRUCTURES IN JAVA"),
        (
            "COMSW1004_001_2026_3 - INTRO-COMPUT SCI/PROG IN JAVA",
            "INTRO-COMPUT SCI/PROG IN JAVA",
        ),
        ("Fall 2026 First Year Japanese I (Section 002)", "First Year Japanese I"),
        ("CS61A Fall 2026", "CS61A Fall 2026"),
    ],
)
def test_course_names_are_shortened(raw, expected):
    assert shorten_course(raw) == expected


def test_a_very_long_course_name_is_truncated():
    from canvas_ddl.digest import COURSE_MAX_CHARS

    out = shorten_course("Introduction to " + "Extremely Long Subject " * 5)
    assert len(out) <= COURSE_MAX_CHARS
    assert out.endswith("…")


def test_shortening_never_returns_empty():
    assert shorten_course("Fall 2026 ") == "Fall 2026"


# --- fetch behaviour --------------------------------------------------------

def test_a_transient_network_failure_is_retried(monkeypatch):
    """A digest that gives up on one blip loses a whole day."""
    import urllib.error

    from canvas_ddl import ics

    attempts = {"n": 0}

    class _Response:
        def read(self, _n):
            return FIXTURE.read_bytes()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def flaky(request, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise urllib.error.URLError("temporary failure")
        return _Response()

    monkeypatch.setattr(ics.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(ics.time, "sleep", lambda _s: None)

    raw = ics.fetch("https://example.instructure.com/feeds/calendars/user_x.ics")
    assert attempts["n"] == 3
    assert b"BEGIN:VCALENDAR" in raw


def test_a_permanent_http_error_is_not_retried(monkeypatch):
    import urllib.error

    from canvas_ddl import ics

    attempts = {"n": 0}

    def gone(request, timeout):
        attempts["n"] += 1
        raise urllib.error.HTTPError("https://redacted", 404, "Not Found", {}, None)

    monkeypatch.setattr(ics.urllib.request, "urlopen", gone)
    monkeypatch.setattr(ics.time, "sleep", lambda _s: None)

    with pytest.raises(ics.FeedError) as caught:
        ics.fetch("https://example.instructure.com/feeds/calendars/user_x.ics")
    assert attempts["n"] == 1
    assert "404" in str(caught.value)
    assert "user_x" not in str(caught.value)


# --- ignore list ------------------------------------------------------------
# Instructors often file class sessions as Canvas assignments, so no machine
# signal separates them from real work. The ignore list is how the user says so.

def test_ignore_list_drops_matching_titles():
    from canvas_ddl.__main__ import apply_ignore_list

    items = [_at(1, title="Lesson 3 Day 1: hiragana"), _at(2, title="Programming Assignment 2")]
    kept, dropped = apply_ignore_list(items, r"^Lesson \d+ Day")
    assert [d.title for d in kept] == ["Programming Assignment 2"]
    assert dropped == 1


def test_ignore_list_accepts_several_patterns():
    from canvas_ddl.__main__ import apply_ignore_list

    items = [_at(1, title="Lesson 1"), _at(2, title="Office Hours"), _at(3, title="Homework 1")]
    kept, dropped = apply_ignore_list(items, "^Lesson\noffice hours")
    assert [d.title for d in kept] == ["Homework 1"]
    assert dropped == 2


def test_empty_ignore_list_keeps_everything():
    from canvas_ddl.__main__ import apply_ignore_list

    items = [_at(1)]
    assert apply_ignore_list(items, "   \n  ") == (items, 0)


def test_a_bad_pattern_is_skipped_not_fatal(capsys):
    """Losing one filter beats losing the whole digest."""
    from canvas_ddl.__main__ import apply_ignore_list

    items = [_at(1, title="Lesson 1"), _at(2, title="Homework 1")]
    kept, dropped = apply_ignore_list(items, "[unclosed\n^Lesson")
    assert [d.title for d in kept] == ["Homework 1"]
    assert dropped == 1
    assert "bad IGNORE_TITLES pattern" in capsys.readouterr().err
