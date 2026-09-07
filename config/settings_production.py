"""本番用の設定。

全通信を HTTPS に限定し、患者情報を載せた Cookie が平文で流れないようにする。
保存データの暗号化は、症状・自由記述のアプリ層暗号化（EncryptedTextField）に加えて
ディスク／RDS の at-rest 暗号化を前提とする。
"""

import os

from config.settings import *  # noqa: F401,F403

DEBUG = False

# --- HTTPS の強制 ---

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000  # 1年
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# TLS を終端するロードバランサ配下で動かす場合に、元の通信方式を伝える。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- その他の防御 ---

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# 本番では開発用の既定値を使わせない。未設定なら起動時に気付けるよう空にしておく。
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")
