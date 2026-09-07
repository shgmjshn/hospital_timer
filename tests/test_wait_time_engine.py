"""要件3: Wait-Time Engine の受入テスト。"""

import re

import pytest

from tests.spec import MSG_COME_TO_ROOM, WAIT_TEXT_PATTERN, jst

pytestmark = pytest.mark.django_db


def test_wait_time_is_the_sum_of_durations_ahead(make_entry, masters):
    from wait_time_engine import engine

    head = make_entry(masters.fever)  # 10分
    second = make_entry(masters.stomach)  # 20分
    target = make_entry(masters.rash)  # 8分（本人の所要時間は待ち時間に含めない）

    assert engine.wait_minutes_for(head) == 0
    assert engine.wait_minutes_for(second) == 10
    assert engine.wait_minutes_for(target) == 30


def test_reserved_priority_is_reflected_in_wait_time(make_entry, masters):
    from queue_store.models import QueueEntry
    from wait_time_engine import engine

    walk_in = make_entry(masters.rash, submitted_at=jst(2026, 9, 2, 9, 5))
    make_entry(
        masters.stomach,
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 2, 11, 0),
        submitted_at=jst(2026, 9, 2, 9, 30),
    )

    assert engine.wait_minutes_for(walk_in) == 20


def test_wait_text_matches_the_required_format(make_entry, masters, clinic_hours):
    from wait_time_engine import engine

    assert engine.format_minutes(18) == "約18分"
    assert re.fullmatch(WAIT_TEXT_PATTERN, engine.format_minutes(18))

    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    assert re.fullmatch(WAIT_TEXT_PATTERN, engine.status_for(second).wait_text)


def test_wait_text_never_uses_a_range_or_omits_the_prefix():
    from wait_time_engine import engine

    text = engine.format_minutes(25)

    assert text.startswith("約")
    assert text.endswith("分")
    for forbidden in ("〜", "~", "-", "から", "以上", "程度"):
        assert forbidden not in text


def test_head_of_queue_gets_the_come_to_room_message_instead_of_zero_minutes(
    make_entry, masters, clinic_hours
):
    """イベントA: 待ち時間が0に到達した患者には事前案内を出す。"""
    from wait_time_engine import engine

    head = make_entry(masters.fever)
    status = engine.status_for(head)

    assert engine.wait_minutes_for(head) == 0
    assert status.phase == engine.Phase.COME_TO_ROOM
    assert status.wait_text is None
    assert MSG_COME_TO_ROOM in status.message


def test_wait_time_is_recalculated_on_every_submission(make_entry, masters):
    from wait_time_engine import engine

    make_entry(masters.fever)  # 10分
    second = make_entry(masters.stomach)  # 20分
    assert engine.wait_minutes_for(second) == 10

    third = make_entry(masters.rash)
    assert engine.wait_minutes_for(third) == 30


def test_wait_time_is_recalculated_on_every_completion(
    make_entry, masters, room, push_transport
):
    from queue_store.services import finish_exam, start_exam
    from wait_time_engine import engine

    head = make_entry(masters.fever)  # 10分
    second = make_entry(masters.stomach)  # 20分
    third = make_entry(masters.rash)
    assert engine.wait_minutes_for(third) == 30

    start_exam(head)
    finish_exam()

    assert engine.wait_minutes_for(second) == 0
    assert engine.wait_minutes_for(third) == 20


def test_position_is_exposed_for_display(make_entry, masters, clinic_hours):
    from wait_time_engine import engine

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)

    assert engine.status_for(head).position == 1
    assert engine.status_for(second).position == 2
