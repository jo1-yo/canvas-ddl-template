import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from canvas_ddl.ics import FeedError, parse

FIXTURE = Path(__file__).parent / "fixtures" / "canvas_sample.ics"
LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def deadlines():
    return parse(FIXTURE.read_bytes(), LA)


def test_recurring_class_meetings_are_dropped(deadlines):
    """A weekly discussion section is not a deadline and would flood every digest."""
    assert all("Discussion Section" not in d.title for d in deadlines)


def test_course_is_split_out_of_the_summary(deadlines):
    lab = next(d for d in deadlines if d.title.startswith("Lab 7"))
    assert lab.title == "Lab 7: Scheme Interpreter"
    assert lab.course == "CS61A Fall 2026"


def test_summary_without_brackets_keeps_whole_title(deadlines):
    office_hours = next(d for d in deadlines if d.title == "Office Hours")
    assert office_hours.course is None


def test_times_are_converted_to_the_target_timezone(deadlines):
    """20260922T065900Z is 23:59 on the 21st in Los Angeles (UTC-7 in September)."""
    lab = next(d for d in deadlines if d.title.startswith("Lab 7"))
    assert lab.due.tzinfo is not None
    assert (lab.due.year, lab.due.month, lab.due.day) == (2026, 9, 21)
    assert (lab.due.hour, lab.due.minute) == (23, 59)
    assert not lab.all_day


def test_all_day_entries_land_at_end_of_that_local_day(deadlines):
    """An all-day item must not drift to the previous day via UTC conversion."""
    reading = next(d for d in deadlines if d.title.startswith("Reading Response"))
    assert reading.all_day
    assert reading.due.date() == dt.date(2026, 9, 24)
    assert (reading.due.hour, reading.due.minute) == (23, 59)


def test_results_are_sorted_by_due_date(deadlines):
    assert deadlines == sorted(deadlines, key=lambda d: d.due)


def test_past_events_are_still_parsed(deadlines):
    """Filtering by time is digest.select's job, not the parser's."""
    assert any(d.title.startswith("Lab 6") for d in deadlines)


def test_garbage_input_raises_feed_error():
    with pytest.raises(FeedError):
        parse(b"this is not a calendar", LA)


def test_assignments_are_told_apart_from_calendar_entries(deadlines):
    """A Canvas feed mixes submittable work with class meetings and office
    hours. Only the first kind belongs in a deadline digest."""
    by_title = {d.title: d for d in deadlines}
    assert by_title["Lab 7: Scheme Interpreter"].is_assignment
    assert by_title["Problem Set 4"].is_assignment
    assert not by_title["Office Hours"].is_assignment


def test_quizzes_and_discussions_count_as_submittable():
    from canvas_ddl.ics import KIND_ASSIGNMENT, _classify

    assert _classify("https://x.instructure.com/courses/1/quizzes/5", "") == KIND_ASSIGNMENT
    assert _classify("https://x.instructure.com/courses/1/discussion_topics/5", "") == KIND_ASSIGNMENT
    assert _classify(None, "event-assignment-123@instructure.com") == KIND_ASSIGNMENT


def test_calendar_events_are_not_submittable():
    from canvas_ddl.ics import KIND_EVENT, _classify

    assert _classify("https://x.instructure.com/calendar_events/9", "") == KIND_EVENT
    assert _classify(None, "event-calendar-event-9@instructure.com") == KIND_EVENT
    assert _classify(None, "") == KIND_EVENT


# Canvas points at the calendar with an anchor rather than at the assignment.

def test_calendar_anchor_links_become_direct_assignment_links():
    from canvas_ddl.ics import direct_link

    raw = (
        "https://canvas.example.edu/calendar"
        "?include_contexts=course_1234&month=09&year=2026#assignment_5678"
    )
    assert direct_link(raw) == (
        "https://canvas.example.edu/courses/1234/assignments/5678"
    )


def test_links_that_do_not_match_are_left_alone():
    from canvas_ddl.ics import direct_link

    for raw in [
        "https://x.instructure.com/courses/1/assignments/5",
        "https://x.instructure.com/calendar?month=09#event_7",
        "https://x.instructure.com/calendar",
        "not a url",
    ]:
        assert direct_link(raw) == raw
