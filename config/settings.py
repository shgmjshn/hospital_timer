"""待ち時間確認システムの設定。

運用値は環境変数で上書きできる。本番用の追加設定は config/settings_production.py。
"""

import os
from pathlib import Path

from config.database import database_config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-K-_H8sZjAmJQKnVBez95-koty1OVwus2Br7ForODdnmnARi6Bkv07Q",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if host.strip()
]
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if _render_host:
    _origin = f"https://{_render_host}"
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "queue_store",
    "intake",
    "wait_time_engine",
    "status_view",
    "notifier",
    "doctor_console",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.display",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": database_config()}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/doctor/login/"
LOGIN_REDIRECT_URL = "/doctor/"
LOGOUT_REDIRECT_URL = "/doctor/login/"

# --- 運用パラメータ（すべて上書き可能） ---

CLINIC_NAME = os.environ.get("CLINIC_NAME", "地域医療クリニック")

# Duration Table に該当がない症状に適用する既定の所要時間（分）
DEFAULT_DURATION_MINUTES = int(os.environ.get("DEFAULT_DURATION_MINUTES", "15"))
# 所要時間の下限（分）。これ未満は保存時に切り上げる
MIN_DURATION_MINUTES = int(os.environ.get("MIN_DURATION_MINUTES", "1"))

# Status View のポーリング間隔（秒）。再計算の反映上限秒数以下でなければならない
STATUS_POLL_INTERVAL_SECONDS = int(os.environ.get("STATUS_POLL_INTERVAL_SECONDS", "5"))
# 「再計算から Status View 反映まで」の上限（秒）
WAIT_TIME_MAX_REFLECT_SECONDS = 10

# Status View の可読性基準（拡大操作なしで読めることの数値基準）
STATUS_VIEW_MIN_BODY_FONT_PX = 16
STATUS_VIEW_WAIT_FONT_PX = 72

# 症状・自由記述を閲覧できる医師ロールのグループ名
DOCTOR_GROUP_NAME = "doctors"

# Web Push
NOTIFIER_PUSH_TRANSPORT = os.environ.get(
    "NOTIFIER_PUSH_TRANSPORT", "notifier.transport.WebPushTransport"
)
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "admin@example.clinic")

# アプリ層のフィールド暗号化キー（Fernet）。本番では必ず環境変数で与える
FIELD_ENCRYPTION_KEY = os.environ.get(
    "FIELD_ENCRYPTION_KEY", "oU43J0WVD8jUT--TV3u9XLRhQKn_do7gEpw41iBV0Kw="
)

# HTTPS 前提。開発では自己署名証明書でローカルHTTPSを起動する
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
