"""エッジケースの受入テスト（閉院時・待ち時間ゼロ・未登録症状）。"""

import re
from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from tests.spec import (
    AFTER_CLOSING,
    DURING_LUNCH_BREAK,
    MSG_CLOSED,
    MSG_NO_WAITING,
    MSG_READY_NOW,
    WAIT_TEXT_IN_PAGE_PATTERN,
    WAIT_TEXT_PATTERN,
    jst,
)

pytestmark = pytest.mark.django_db


def test_closed_hours_hide_the_wait_time_and_show_the_next_reception(
    fresh_client, make_entry, clinic_hours
):
    entry = make_entry()

    with freeze_time(AFTER_CLOSING):
        response = fresh_client.get(reverse("status_view:detail", args=[entry.pk]))
        content = response.content.decode()
        state = fresh_client.get(reverse("status_view:state", args=[entry.pk])).json()

    assert response.status_code == 200
    assert MSG_CLOSED in content
    assert not re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)
    assert "09:00" in content
    assert state["phase"] == "closed"
    assert state["wait_text"] is None


def test_closed_hours_block_intake_submission(fresh_client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    with freeze_time(AFTER_CLOSING):
        form = fresh_client.get(reverse("intake:form"))
        response = fresh_client.post(reverse("intake:form"), data=intake_payload())

    assert MSG_CLOSED in form.content.decode()
    assert response.status_code == 403
    assert QueueEntry.objects.count() == 0


def test_closure_day_blocks_intake_submission(fresh_client, clinic_hours, intake_payload):
    """曜日設定に加えて臨時休診日の設定も受付停止として扱う。"""
    from queue_store.models import ClinicClosure, QueueEntry

    ClinicClosure.objects.create(date=date(2026, 9, 2), reason="臨時休診")

    response = fresh_client.post(reverse("intake:form"), data=intake_payload())

    assert response.status_code == 403
    assert QueueEntry.objects.count() == 0


def test_lunch_break_blocks_submission_but_keeps_showing_the_wait_time(
    fresh_client, make_entry, masters, clinic_hours, intake_payload
):
    """昼休みは受付を止めるが、待機中の患者には待ち時間を出し続ける。"""
    from queue_store.models import QueueEntry

    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    with freeze_time(DURING_LUNCH_BREAK):
        response = fresh_client.post(reverse("intake:form"), data=intake_payload())
        content = fresh_client.get(
            reverse("status_view:detail", args=[second.pk])
        ).content.decode()

    assert response.status_code == 403
    assert QueueEntry.objects.count() == 2
    assert re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)


def test_next_reception_time_is_the_next_open_slot(clinic_hours):
    from queue_store import hours

    with freeze_time(AFTER_CLOSING):
        assert hours.is_reception_open() is False
        assert hours.next_open_at() == jst(2026, 9, 3, 9, 0)


def test_empty_queue_shows_the_no_waiting_message_instead_of_zero_minutes(
    fresh_client, clinic_hours, masters
):
    response = fresh_client.get(reverse("status_view:lobby"))
    content = response.content.decode()

    assert response.status_code == 200
    assert MSG_NO_WAITING in content
    assert MSG_READY_NOW in content
    assert "約0分" not in content
    assert not re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)


def test_lobby_shows_the_total_wait_time_when_the_queue_is_not_empty(
    fresh_client, make_entry, masters, clinic_hours
):
    make_entry(masters.fever)
    make_entry(masters.stomach)

    content = fresh_client.get(reverse("status_view:lobby")).content.decode()

    assert "約30分" in content
    assert MSG_NO_WAITING not in content


def test_overall_status_reports_an_empty_queue(clinic_hours, masters):
    from wait_time_engine import engine

    status = engine.overall_status()

    assert status.phase == engine.Phase.QUEUE_EMPTY
    assert status.wait_text is None
    assert MSG_NO_WAITING in status.message


def test_unregistered_symptom_uses_the_default_duration(
    make_entry, masters, settings, clinic_hours
):
    from wait_time_engine import engine

    make_entry(masters.unregistered)
    target = make_entry(masters.fever)

    assert engine.wait_minutes_for(target) == settings.DEFAULT_DURATION_MINUTES
    assert re.fullmatch(WAIT_TEXT_PATTERN, engine.status_for(target).wait_text)


def test_unregistered_symptom_records_an_operator_alert(make_entry, masters, settings):
    from queue_store.models import UnregisteredSymptomAlert
    from wait_time_engine import engine

    entry = make_entry(masters.unregistered)
    engine.wait_minutes_for(entry)

    alert = UnregisteredSymptomAlert.objects.filter(symptom=masters.unregistered).first()
    assert alert is not None
    assert alert.applied_minutes == settings.DEFAULT_DURATION_MINUTES
    assert alert.acknowledged is False


def test_unregistered_symptom_does_not_break_submission(
    client, clinic_hours, masters, intake_payload
):
    from queue_store.models import QueueEntry, UnregisteredSymptomAlert

    response = client.post(
        reverse("intake:form"), data=intake_payload(symptom=str(masters.unregistered.pk))
    )

    assert response.status_code == 302
    assert QueueEntry.objects.count() == 1
    assert UnregisteredSymptomAlert.objects.exists()


def test_unregistered_symptom_alert_is_visible_in_the_admin(admin_client, make_entry, masters):
    from wait_time_engine import engine

    entry = make_entry(masters.unregistered)
    engine.wait_minutes_for(entry)

    response = admin_client.get(
        reverse("admin:queue_store_unregisteredsymptomalert_changelist")
    )

    assert response.status_code == 200
    assert masters.unregistered.name in response.content.decode()
