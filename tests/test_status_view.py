"""要件4: Status View の受入テスト（到達性・可読性・リンク寿命）。"""

import re
import uuid

import pytest
from django.conf import settings
from django.urls import reverse

from tests.spec import (
    MSG_FINISHED,
    WAIT_TEXT_IN_PAGE_PATTERN,
    WAIT_TEXT_PATTERN,
    jst,
)

pytestmark = pytest.mark.django_db


def test_reachable_without_login_registration_or_cookies(fresh_client, make_entry, clinic_hours):
    entry = make_entry()
    assert not fresh_client.cookies

    response = fresh_client.get(reverse("status_view:detail", args=[entry.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'type="password"' not in content
    assert settings.LOGIN_URL not in content


def test_state_endpoint_is_reachable_without_login(fresh_client, make_entry, clinic_hours):
    entry = make_entry()

    response = fresh_client.get(reverse("status_view:state", args=[entry.pk]))

    assert response.status_code == 200
    assert response.json()["poll_interval_seconds"] == settings.STATUS_POLL_INTERVAL_SECONDS


def test_page_shows_wait_time_in_the_required_format(fresh_client, make_entry, masters, clinic_hours):
    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    response = fresh_client.get(reverse("status_view:detail", args=[second.pk]))
    content = response.content.decode()

    assert "約10分" in content
    assert re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)


def test_state_json_wait_text_matches_the_required_format(fresh_client, make_entry, masters, clinic_hours):
    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    state = fresh_client.get(reverse("status_view:state", args=[second.pk])).json()

    assert re.fullmatch(WAIT_TEXT_PATTERN, state["wait_text"])
    assert state["position"] == 2


def test_no_text_input_is_needed_to_read_the_wait_time(fresh_client, make_entry, masters, clinic_hours):
    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    content = fresh_client.get(reverse("status_view:detail", args=[second.pk])).content.decode()

    assert "<textarea" not in content
    assert 'type="text"' not in content
    assert 'type="search"' not in content


def test_wait_time_is_readable_without_zooming(fresh_client, make_entry, masters, clinic_hours):
    make_entry(masters.fever)
    second = make_entry(masters.stomach)

    content = fresh_client.get(reverse("status_view:detail", args=[second.pk])).content.decode()

    body_px = int(re.search(r"--body-font-size:\s*(\d+)px", content).group(1))
    wait_px = int(re.search(r"--wait-font-size:\s*(\d+)px", content).group(1))

    assert body_px >= settings.STATUS_VIEW_MIN_BODY_FONT_PX
    assert wait_px == settings.STATUS_VIEW_WAIT_FONT_PX
    assert wait_px >= 2 * body_px
    assert 'name="viewport"' in content


def test_page_declares_the_polling_interval(fresh_client, make_entry, clinic_hours):
    entry = make_entry()

    content = fresh_client.get(reverse("status_view:detail", args=[entry.pk])).content.decode()

    assert f'data-poll-interval="{settings.STATUS_POLL_INTERVAL_SECONDS}"' in content


def test_same_screen_at_home_and_in_the_waiting_room(make_entry, masters, clinic_hours):
    from django.test import Client

    make_entry(masters.fever)
    second = make_entry(masters.stomach)
    url = reverse("status_view:state", args=[second.pk])

    at_home = Client(HTTP_USER_AGENT="Mozilla/5.0 (iPhone)").get(url).json()
    in_waiting_room = Client(HTTP_USER_AGENT="Mozilla/5.0 (Android)").get(url).json()

    assert at_home == in_waiting_room


def test_recalculation_is_reflected_immediately(
    fresh_client, make_entry, masters, clinic_hours, room, push_transport
):
    """再計算はキャッシュされず、次のポーリングで必ず新しい値になる。"""
    from queue_store.services import finish_exam, start_exam

    head = make_entry(masters.fever)
    second = make_entry(masters.stomach)
    third = make_entry(masters.rash)
    url = reverse("status_view:state", args=[third.pk])

    assert fresh_client.get(url).json()["wait_text"] == "約30分"

    start_exam(head)
    finish_exam()

    assert fresh_client.get(url).json()["wait_text"] == "約20分"


def test_finished_entry_shows_the_finished_message(fresh_client, make_entry, masters, clinic_hours):
    """リンク寿命: 診察終了後にリンクを開くと終了案内を表示する。"""
    from queue_store.models import QueueEntry

    entry = make_entry(masters.fever, status=QueueEntry.Status.DONE)

    response = fresh_client.get(reverse("status_view:detail", args=[entry.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert MSG_FINISHED in content
    assert not re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)


def test_future_reservation_shows_the_reservation_time_instead_of_a_wait_time(
    fresh_client, make_entry, masters, clinic_hours
):
    """予約日が当日でなくてもリンクは有効で、待ち時間ではなく予約日時を示す。"""
    from queue_store.models import QueueEntry

    entry = make_entry(
        masters.fever,
        visit_type=QueueEntry.VisitType.RESERVED,
        reserved_at=jst(2026, 9, 3, 10, 0),
    )

    response = fresh_client.get(reverse("status_view:detail", args=[entry.pk]))
    content = response.content.decode()
    state = fresh_client.get(reverse("status_view:state", args=[entry.pk])).json()

    assert response.status_code == 200
    assert "9月3日" in content
    assert "10:00" in content
    assert not re.search(WAIT_TEXT_IN_PAGE_PATTERN, content)
    assert state["phase"] == "scheduled_future"


def test_unknown_identifier_returns_404(fresh_client, clinic_hours):
    response = fresh_client.get(reverse("status_view:detail", args=[uuid.uuid4()]))

    assert response.status_code == 404
