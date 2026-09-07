"""デプロイ用ヘルスチェックの受入テスト。DB は使わない。"""

import importlib

from django.test import Client


def test_healthz_returns_ok_without_redirect():
    response = Client().get("/healthz")

    assert response.status_code == 200
    assert response.content == b"ok"


def test_production_healthz_skips_ssl_redirect():
    production = importlib.import_module("config.settings_production")

    assert any("healthz" in pattern for pattern in production.SECURE_REDIRECT_EXEMPT)
