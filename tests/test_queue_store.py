"""要件2: Queue Store（並び順・Duration Table）の受入テスト。"""

import pytest
from django.core.exceptions import ValidationError

from tests.spec import jst

pytestmark = pytest.mark.django_db


def test_reserved_patients_are_placed_before_walk_ins(make_entry, masters):
    from queue_store.models import QueueEntry
    from queue_store.ordering import waiting_queue

    walk_in = make_entry(submitted_at=jst(2026, 9, 2, 9, 5))
    reserved = make_entry(
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 2, 11, 0),
        submitted_at=jst(2026, 9, 2, 9, 30),
    )

    assert list(waiting_queue()) == [reserved, walk_in]


def test_reserved_patients_are_ordered_by_reservation_time_not_submission(make_entry):
    """予約時刻の早い予約者は、提出が遅くても先に並ぶ。"""
    from queue_store.models import QueueEntry
    from queue_store.ordering import waiting_queue

    later_slot = make_entry(
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 2, 11, 30),
        submitted_at=jst(2026, 9, 2, 8, 40),
    )
    earlier_slot = make_entry(
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 2, 10, 30),
        submitted_at=jst(2026, 9, 2, 9, 55),
    )

    assert list(waiting_queue()) == [earlier_slot, later_slot]


def test_walk_ins_are_ordered_by_arrival(make_entry):
    from queue_store.ordering import waiting_queue

    second = make_entry(submitted_at=jst(2026, 9, 2, 9, 20))
    first = make_entry(submitted_at=jst(2026, 9, 2, 9, 10))
    third = make_entry(submitted_at=jst(2026, 9, 2, 9, 40))

    assert list(waiting_queue()) == [first, second, third]


def test_only_todays_entries_are_in_the_queue(make_entry):
    """翌日以降の予約は当日の待機列に含めない。"""
    from queue_store.models import QueueEntry
    from queue_store.ordering import waiting_queue

    today = make_entry(
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 2, 11, 0),
    )
    tomorrow = make_entry(
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 3, 10, 0),
    )

    queue = list(waiting_queue())
    assert today in queue
    assert tomorrow not in queue


def test_entry_under_examination_stays_at_the_head(make_entry):
    """診察中の患者は待機列に残り、後続の待ち時間に算入される。"""
    from queue_store.models import QueueEntry
    from queue_store.ordering import waiting_queue

    head = make_entry(status=QueueEntry.Status.IN_EXAM)
    following = make_entry()

    assert list(waiting_queue()) == [head, following]


def test_finished_entry_leaves_the_queue(make_entry):
    from queue_store.models import QueueEntry
    from queue_store.ordering import waiting_queue

    finished = make_entry(status=QueueEntry.Status.DONE)
    waiting = make_entry()

    assert list(waiting_queue()) == [waiting]
    assert finished not in list(waiting_queue())


def test_duration_table_can_be_updated_with_measured_values(masters):
    """Duration Table は実測値で更新できる。"""
    duration = masters.fever.duration
    assert duration.duration_minutes == 10

    duration.record_actual(18)
    duration.refresh_from_db()
    assert duration.duration_minutes == 18
    assert duration.sample_count == 1

    duration.record_actual(10)
    duration.refresh_from_db()
    assert duration.duration_minutes == 14
    assert duration.sample_count == 2


def test_duration_table_can_be_updated_manually(masters):
    duration = masters.rash.duration
    duration.duration_minutes = 12
    duration.save()
    duration.refresh_from_db()

    assert duration.duration_minutes == 12


def test_duration_below_one_minute_is_clamped_on_save(masters, settings):
    """1分未満を登録しようとしても実効値は1分以上になる。"""
    duration = masters.rash.duration
    duration.duration_minutes = 0
    duration.save()
    duration.refresh_from_db()

    assert duration.duration_minutes >= settings.MIN_DURATION_MINUTES
    assert duration.duration_minutes == 1


def test_duration_below_one_minute_is_clamped_on_create(masters):
    from queue_store.models import SymptomDuration

    created = SymptomDuration.objects.create(symptom=masters.unregistered, duration_minutes=0)
    created.refresh_from_db()

    assert created.duration_minutes == 1


def test_measured_value_below_one_minute_is_clamped(masters):
    duration = masters.fever.duration
    duration.record_actual(0)
    duration.refresh_from_db()

    assert duration.duration_minutes == 1


def test_duration_below_one_minute_is_rejected_by_validation(masters):
    """管理画面などの入力経路では1分未満をエラーにする。"""
    duration = masters.fever.duration
    duration.duration_minutes = 0

    with pytest.raises(ValidationError):
        duration.full_clean()
