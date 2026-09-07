"""要件1: Intake Form の受入テスト。"""

import re

import pytest
from django.urls import reverse

from tests.spec import jst

pytestmark = pytest.mark.django_db

# 仕様が必須と定める入力項目（来院区分は保持が必須のため同様に扱う）
REQUIRED_FIELDS = ["full_name", "kana", "age_band", "gender", "symptom", "visit_type"]


def tag_with_attribute(content, attribute):
    """指定属性を持つ最初のHTML要素の開始タグを返す。"""
    match = re.search(rf"<[^>]*{re.escape(attribute)}[^>]*>", content)
    assert match, f"{attribute} を持つ要素が見つからない"
    return match.group(0)


def test_submission_creates_queue_entry_and_issues_uuid_v4_link(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    response = client.post(reverse("intake:form"), data=intake_payload())

    assert response.status_code == 302
    entry = QueueEntry.objects.get()
    assert entry.id.version == 4
    assert response["Location"] == reverse("status_view:detail", args=[entry.pk])


def test_temporary_identifier_is_not_sequential(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    assert QueueEntry._meta.pk.get_internal_type() == "UUIDField"

    client.post(reverse("intake:form"), data=intake_payload())
    client.post(reverse("intake:form"), data=intake_payload(full_name="鈴木 一郎"))

    identifiers = [entry.pk for entry in QueueEntry.objects.all()]
    assert len(set(identifiers)) == 2
    assert all(identifier.version == 4 for identifier in identifiers)


@pytest.mark.parametrize("missing_field", REQUIRED_FIELDS)
def test_empty_required_field_is_rejected(client, clinic_hours, intake_payload, missing_field):
    from queue_store.models import QueueEntry

    response = client.post(reverse("intake:form"), data=intake_payload(**{missing_field: ""}))

    assert response.status_code == 200
    assert QueueEntry.objects.count() == 0
    assert response.context["form"].errors[missing_field]


def test_submission_succeeds_with_empty_free_text(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    response = client.post(reverse("intake:form"), data=intake_payload(free_text=""))

    assert response.status_code == 302
    assert QueueEntry.objects.get().free_text == ""


def test_free_text_is_stored_when_provided(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    client.post(reverse("intake:form"), data=intake_payload(free_text="3日前から咳もある"))

    assert QueueEntry.objects.get().free_text == "3日前から咳もある"


def test_free_text_field_is_hidden_until_symptom_is_selected(client, clinic_hours):
    response = client.get(reverse("intake:form"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "hidden" in tag_with_attribute(content, 'data-reveal-when="symptom"')


def test_free_text_without_symptom_is_rejected(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    response = client.post(
        reverse("intake:form"), data=intake_payload(symptom="", free_text="頭も痛い")
    )

    assert response.status_code == 200
    assert QueueEntry.objects.count() == 0


def test_visit_type_is_preserved(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    client.post(
        reverse("intake:form"),
        data=intake_payload(
            visit_type=QueueEntry.VisitType.RESERVED, reserved_at="2026-09-02T11:00"
        ),
    )

    entry = QueueEntry.objects.get()
    assert entry.visit_type == QueueEntry.VisitType.RESERVED
    assert entry.reserved_at == jst(2026, 9, 2, 11, 0)


def test_walk_in_submission_keeps_visit_type(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    client.post(reverse("intake:form"), data=intake_payload())

    assert QueueEntry.objects.get().visit_type == QueueEntry.VisitType.WALK_IN


def test_reserved_visit_requires_reservation_time(client, clinic_hours, intake_payload):
    from queue_store.models import QueueEntry

    response = client.post(
        reverse("intake:form"),
        data=intake_payload(visit_type=QueueEntry.VisitType.RESERVED, reserved_at=""),
    )

    assert response.status_code == 200
    assert QueueEntry.objects.count() == 0
    assert response.context["form"].errors["reserved_at"]


def test_reservation_time_field_is_hidden_until_reserved_visit_is_chosen(client, clinic_hours):
    response = client.get(reverse("intake:form"))
    content = response.content.decode()

    assert "hidden" in tag_with_attribute(content, 'data-reveal-when="visit_type=reserved"')
