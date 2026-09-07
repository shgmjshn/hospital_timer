"""要件5: Notifier の受入テスト（2段階の呼び出しと診察中フラグ）。"""

import re

import pytest
from django.urls import reverse

from tests.spec import (
    MSG_COME_TO_ROOM,
    MSG_FINAL_CALL,
    MSG_NO_WAITING,
    WAIT_TEXT_IN_PAGE_PATTERN,
)

pytestmark = pytest.mark.django_db


def test_no_notification_is_sent_before_a_completion_is_recorded(
    make_entry, masters, room, push_transport, make_push_subscription
):
    """診察完了記録がない間、通知送信件数は0。"""
    from notifier.models import NotificationLog
    from queue_store.services import start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    make_push_subscription(second)

    start_exam(head)

    assert NotificationLog.objects.count() == 0
    assert push_transport.sent == []


def test_completion_sends_exactly_one_final_call_to_the_next_patient(
    make_entry, masters, room, push_transport, make_push_subscription
):
    """イベントB: 手が空いた時点で、削除後の待機列先頭へ1件だけ送る。"""
    from notifier.models import NotificationLog
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    third = make_entry(masters.rash)
    make_push_subscription(second)
    make_push_subscription(third)

    start_exam(head)
    finish_exam()

    logs = list(NotificationLog.objects.filter(kind=NotificationLog.Kind.FINAL_CALL))
    assert len(logs) == 1
    assert logs[0].entry_id == second.pk
    assert logs[0].channel == NotificationLog.Channel.WEB_PUSH
    assert len(push_transport.sent) == 1
    assert push_transport.sent[0]["endpoint"].endswith(str(second.pk))
    assert MSG_FINAL_CALL in push_transport.sent[0]["payload"]["body"]


def test_no_final_call_while_the_doctor_is_in_exam(
    make_entry, masters, room, push_transport, make_push_subscription
):
    """診察中フラグが true の間は確定呼出を送らない。"""
    from notifier import dispatcher
    from notifier.models import NotificationLog
    from queue_store.models import ConsultationRoomState
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    third = make_entry(masters.rash)
    for entry in (second, third):
        make_push_subscription(entry)

    start_exam(head)
    finish_exam()
    assert NotificationLog.objects.count() == 1

    start_exam(second)
    assert ConsultationRoomState.load().is_in_exam is True

    assert dispatcher.dispatch_final_call() is None
    assert NotificationLog.objects.count() == 1
    assert len(push_transport.sent) == 1


def test_final_call_is_not_duplicated_for_the_same_patient(
    make_entry, masters, room, push_transport, make_push_subscription
):
    """手が空いている状態で再度ディスパッチしても、同じ患者へ二重に送らない。"""
    from notifier import dispatcher
    from notifier.models import NotificationLog
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    make_push_subscription(second)

    start_exam(head)
    finish_exam()
    assert NotificationLog.objects.count() == 1

    assert dispatcher.dispatch_final_call() is None
    assert NotificationLog.objects.count() == 1
    assert len(push_transport.sent) == 1


def test_completed_entry_is_removed_from_the_queue(
    make_entry, masters, room, push_transport
):
    from queue_store.models import ConsultationRoomState, QueueEntry
    from queue_store.ordering import waiting_queue
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)

    start_exam(head)
    finish_exam()

    head.refresh_from_db()
    assert head.status == QueueEntry.Status.DONE
    assert head.finished_at is not None
    assert list(waiting_queue()) == [second]
    assert ConsultationRoomState.load().is_in_exam is False


def test_event_a_is_shown_without_sending_any_push(
    fresh_client, make_entry, masters, clinic_hours, push_transport
):
    """イベントA: 待ち時間0に到達した患者へ画面表示のみを行う。"""
    from notifier.models import NotificationLog

    entry = make_entry(masters.fever)

    content = fresh_client.get(reverse("status_view:detail", args=[entry.pk])).content.decode()

    assert MSG_COME_TO_ROOM in content
    assert MSG_NO_WAITING not in content
    assert not re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)
    assert NotificationLog.objects.count() == 0
    assert push_transport.sent == []


def test_event_a_appears_when_the_patient_reaches_the_head_of_the_queue(
    fresh_client, make_entry, masters, clinic_hours, room, push_transport
):
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    url = reverse("status_view:detail", args=[second.pk])

    assert MSG_COME_TO_ROOM not in fresh_client.get(url).content.decode()

    start_exam(head)
    finish_exam()

    assert MSG_COME_TO_ROOM in fresh_client.get(url).content.decode()


def test_final_call_falls_back_to_in_page_display_when_push_is_not_permitted(
    fresh_client, make_entry, masters, clinic_hours, room, push_transport
):
    """Web Push 未許可の場合は画面内表示に切り替える。"""
    from notifier.models import NotificationLog
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)

    start_exam(head)
    finish_exam()

    log = NotificationLog.objects.get()
    assert log.entry_id == second.pk
    assert log.channel == NotificationLog.Channel.IN_PAGE
    assert push_transport.sent == []

    state = fresh_client.get(reverse("status_view:state", args=[second.pk])).json()
    assert state["final_call"] is True
    assert MSG_FINAL_CALL in state["message"]


def test_completion_recorded_in_the_doctor_console_triggers_one_notification(
    doctor_client, make_entry, masters, room, push_transport, make_push_subscription
):
    """医師の「診察完了」記録がトリガーになる。"""
    from notifier.models import NotificationLog

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    make_push_subscription(second)

    doctor_client.post(reverse("doctor_console:start_exam", args=[head.pk]))
    assert NotificationLog.objects.count() == 0

    response = doctor_client.post(reverse("doctor_console:finish_exam", args=[head.pk]))

    assert response.status_code in (200, 302)
    assert NotificationLog.objects.filter(kind=NotificationLog.Kind.FINAL_CALL).count() == 1
    assert len(push_transport.sent) == 1


def test_push_subscription_can_be_registered_from_the_status_view(
    fresh_client, make_entry, masters, clinic_hours
):
    """Status View 初回表示時の通知許可を購読として保存できる。"""
    from notifier.models import PushSubscription

    entry = make_entry(masters.fever)

    response = fresh_client.post(
        reverse("notifier:subscribe", args=[entry.pk]),
        data={
            "endpoint": "https://push.example.test/registered",
            "keys": {"p256dh": "browser-p256dh", "auth": "browser-auth"},
        },
        content_type="application/json",
    )

    assert response.status_code in (200, 201)
    subscription = PushSubscription.objects.get(entry=entry)
    assert subscription.endpoint == "https://push.example.test/registered"


def test_status_view_offers_the_notification_permission_prompt(
    fresh_client, make_entry, masters, clinic_hours
):
    entry = make_entry(masters.fever)

    content = fresh_client.get(reverse("status_view:detail", args=[entry.pk])).content.decode()

    assert 'data-push-permission-prompt' in content
    assert reverse("notifier:subscribe", args=[entry.pk]) in content
