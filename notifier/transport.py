"""Web Push の送信トランスポート。

`settings.NOTIFIER_PUSH_TRANSPORT` で差し替える。テストでは MemoryTransport を使い、
送信内容を検証する。購読は `endpoint` / `p256dh` / `auth` を持つオブジェクトであれば
何でもよい（Notifier のモデルに依存しない）。
"""

import json
import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class WebPushTransport:
    """pywebpush による実送信。"""

    def send(self, subscription, payload):
        from pywebpush import WebPushException, webpush

        if not settings.VAPID_PRIVATE_KEY:
            logger.warning("VAPID_PRIVATE_KEY が未設定のため Web Push を送信できません。")
            return False
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIM_EMAIL}"},
            )
        except WebPushException as exc:
            logger.warning("Web Push の送信に失敗しました: %s", exc)
            return False
        return True


class MemoryTransport:
    """テスト用。送信内容をクラス変数に記録するだけで、外部へは送らない。"""

    sent = []

    @classmethod
    def reset(cls):
        cls.sent.clear()

    def send(self, subscription, payload):
        type(self).sent.append({"endpoint": subscription.endpoint, "payload": payload})
        return True


def get_transport():
    return import_string(settings.NOTIFIER_PUSH_TRANSPORT)()
