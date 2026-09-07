"""要件6: 症状・自由記述の閲覧権限に対する受入テスト。"""

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

FREE_TEXT = "昨夜から痛みが続いている"


def test_doctor_can_read_symptom_and_free_text(doctor_client, make_entry, masters):
    entry = make_entry(masters.stomach, free_text=FREE_TEXT)

    response = doctor_client.get(reverse("doctor_console:entry_detail", args=[entry.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert masters.stomach.name in content
    assert FREE_TEXT in content


def test_doctor_can_see_the_waiting_queue(doctor_client, make_entry, masters):
    make_entry(masters.stomach, full_name="患者 一郎")

    response = doctor_client.get(reverse("doctor_console:queue"))

    assert response.status_code == 200
    assert "患者 一郎" in response.content.decode()


def test_anonymous_request_does_not_return_clinical_data(fresh_client, make_entry, masters):
    entry = make_entry(masters.stomach, free_text=FREE_TEXT)

    response = fresh_client.get(reverse("doctor_console:entry_detail", args=[entry.pk]))
    content = response.content.decode(errors="ignore")

    assert response.status_code in (302, 403)
    if response.status_code == 302:
        assert settings.LOGIN_URL in response["Location"]
    assert masters.stomach.name not in content
    assert FREE_TEXT not in content


def test_authenticated_non_doctor_does_not_return_clinical_data(
    non_doctor_client, make_entry, masters
):
    entry = make_entry(masters.stomach, free_text=FREE_TEXT)

    response = non_doctor_client.get(reverse("doctor_console:entry_detail", args=[entry.pk]))
    content = response.content.decode(errors="ignore")

    assert response.status_code == 403
    assert masters.stomach.name not in content
    assert FREE_TEXT not in content


def test_patient_status_view_never_exposes_clinical_data(
    fresh_client, make_entry, masters, clinic_hours
):
    make_entry(masters.fever)
    second = make_entry(masters.stomach, free_text=FREE_TEXT)

    page = fresh_client.get(reverse("status_view:detail", args=[second.pk])).content.decode()
    state = fresh_client.get(reverse("status_view:state", args=[second.pk])).json()

    assert masters.stomach.name not in page
    assert FREE_TEXT not in page
    assert FREE_TEXT not in str(state)
    assert masters.stomach.name not in str(state)
    assert "symptom" not in state
    assert "free_text" not in state


def test_non_doctor_cannot_record_a_completion(
    non_doctor_client, make_entry, masters, room, push_transport
):
    from notifier.models import NotificationLog
    from queue_store.models import ConsultationRoomState
    from queue_store.services import start_exam

    head = make_entry(masters.fever)
    make_entry(masters.stomach)
    start_exam(head)

    response = non_doctor_client.post(reverse("doctor_console:finish_exam", args=[head.pk]))

    assert response.status_code == 403
    assert ConsultationRoomState.load().is_in_exam is True
    assert NotificationLog.objects.count() == 0


def test_ensure_operators_creates_a_doctor_admin(settings, db):
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    call_command(
        "ensure_operators",
        stdout=__import__("io").StringIO(),
    )
    # 環境変数が空なら何も作らない
    assert get_user_model().objects.filter(username="render-admin").count() == 0

    settings.DOCTOR_GROUP_NAME = settings.DOCTOR_GROUP_NAME
    monkey_env = {
        "DJANGO_SUPERUSER_USERNAME": "render-admin",
        "DJANGO_SUPERUSER_PASSWORD": "render-admin-pass",
        "DJANGO_SUPERUSER_EMAIL": "admin@example.clinic",
    }
    import os

    for key, value in monkey_env.items():
        os.environ[key] = value
    try:
        call_command("ensure_operators", stdout=__import__("io").StringIO())
        user = get_user_model().objects.get(username="render-admin")
        assert user.is_superuser
        assert user.groups.filter(name=settings.DOCTOR_GROUP_NAME).exists()
        assert user.check_password("render-admin-pass")
        # 再実行してもパスワードは変えない
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = "changed-later"
        call_command("ensure_operators", stdout=__import__("io").StringIO())
        user.refresh_from_db()
        assert user.check_password("render-admin-pass")
    finally:
        for key in monkey_env:
            os.environ.pop(key, None)
