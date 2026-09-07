"""セキュリティ制約の受入テスト（保存時暗号化・キャッシュ・HTTPS）。"""

import importlib

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

SECRET_NAME = "秘密 太郎"
SECRET_KANA = "ヒミツ タロウ"
SECRET_FREE_TEXT = "健康診断の結果について相談したい"


def test_name_and_free_text_are_encrypted_at_rest(make_entry, masters):
    from django.db import connection
    from queue_store.models import QueueEntry

    entry = make_entry(
        masters.stomach,
        full_name=SECRET_NAME,
        kana=SECRET_KANA,
        free_text=SECRET_FREE_TEXT,
    )
    table = QueueEntry._meta.db_table

    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT full_name, kana, free_text FROM "{table}" WHERE id = %s', [str(entry.pk)]
        )
        stored_values = cursor.fetchone()

    for stored in stored_values:
        assert SECRET_NAME not in str(stored)
        assert SECRET_KANA not in str(stored)
        assert SECRET_FREE_TEXT not in str(stored)

    entry.refresh_from_db()
    assert entry.full_name == SECRET_NAME
    assert entry.free_text == SECRET_FREE_TEXT


def test_status_view_is_not_cached_and_not_indexed(fresh_client, make_entry, clinic_hours):
    entry = make_entry()

    response = fresh_client.get(reverse("status_view:detail", args=[entry.pk]))

    assert "no-store" in response["Cache-Control"]
    assert "noindex" in response["X-Robots-Tag"]


def test_state_endpoint_is_not_cached(fresh_client, make_entry, clinic_hours):
    entry = make_entry()

    response = fresh_client.get(reverse("status_view:state", args=[entry.pk]))

    assert "no-store" in response["Cache-Control"]


def test_production_settings_enforce_https():
    production = importlib.import_module("config.settings_production")

    assert production.DEBUG is False
    assert production.SECURE_SSL_REDIRECT is True
    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.SECURE_HSTS_SECONDS >= 31_536_000
