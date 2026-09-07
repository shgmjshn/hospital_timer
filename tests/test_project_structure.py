"""技術スタックと構成要素の命名に対する受入テスト。"""

from django.conf import settings

# 仕様が名前を指定している構成要素
REQUIRED_COMPONENTS = [
    "intake",
    "queue_store",
    "wait_time_engine",
    "status_view",
    "notifier",
]


def test_required_components_are_installed_as_apps():
    for component in REQUIRED_COMPONENTS:
        assert component in settings.INSTALLED_APPS


def test_database_is_postgresql():
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_clinic_timezone_is_asia_tokyo():
    assert settings.TIME_ZONE == "Asia/Tokyo"
    assert settings.USE_TZ is True


def test_reflect_limit_and_poll_interval_are_consistent():
    """「10秒以内に反映」を満たすポーリング間隔が設定されている。"""
    assert settings.WAIT_TIME_MAX_REFLECT_SECONDS <= 10
    assert 0 < settings.STATUS_POLL_INTERVAL_SECONDS <= settings.WAIT_TIME_MAX_REFLECT_SECONDS


def test_readability_thresholds_are_defined():
    """「拡大操作なしに読める」を数値基準として保持している。"""
    assert settings.STATUS_VIEW_MIN_BODY_FONT_PX >= 16
    assert settings.STATUS_VIEW_WAIT_FONT_PX >= 2 * settings.STATUS_VIEW_MIN_BODY_FONT_PX


def test_default_and_minimum_duration_are_configurable():
    assert settings.DEFAULT_DURATION_MINUTES >= 1
    assert settings.MIN_DURATION_MINUTES == 1


def test_database_url_is_parsed_for_cloud_postgres():
    from config.database import database_from_url

    config = database_from_url(
        "postgres://timer:s3cret@example.render.com:5432/hospital_timer"
    )

    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "hospital_timer"
    assert config["USER"] == "timer"
    assert config["PASSWORD"] == "s3cret"
    assert config["HOST"] == "example.render.com"
    assert config["OPTIONS"]["sslmode"] == "require"


def test_local_database_url_does_not_force_tls():
    from config.database import database_from_url

    config = database_from_url("postgres://hospital_timer:hospital_timer@127.0.0.1:55432/hospital_timer")

    assert config["HOST"] == "127.0.0.1"
    assert "sslmode" not in config.get("OPTIONS", {})
