"""アプリ層のフィールド暗号化。

保存データは at-rest 暗号化を前提としつつ、氏名・フリガナ・自由記述は
アプリ層でも暗号化し、データベースを直接参照しても平文が読めない状態にする。
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=8)
def _build_cipher(keys):
    try:
        ciphers = [Fernet(key) for key in keys]
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY が Fernet 鍵として不正です。"
            "Fernet.generate_key() で生成した値を設定してください。"
        ) from exc
    return MultiFernet(ciphers) if len(ciphers) > 1 else ciphers[0]


def get_cipher():
    """暗号化には先頭の鍵を使い、残りの鍵は復号にのみ使う（鍵のローテーション用）。"""
    configured = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if isinstance(configured, (list, tuple)):
        candidates = configured
    else:
        candidates = str(configured).split(",")
    keys = tuple(key.strip() for key in candidates if key and key.strip())
    if not keys:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY が設定されていません。")
    return _build_cipher(keys)


class EncryptedTextField(models.TextField):
    """Fernet で暗号化して保存するテキストフィールド。

    暗号文は同じ平文でも毎回変わるため、この項目に対する等価検索・並び替え・
    集計はできない。検索が必要な項目には使わない。
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        return get_cipher().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        try:
            return get_cipher().decrypt(str(value).encode()).decode()
        except InvalidToken as exc:
            raise ValueError(
                f"{self.name} を復号できません。FIELD_ENCRYPTION_KEY を確認してください。"
            ) from exc
