"""確定呼出（イベントB）のディスパッチ。

医師の手が空いた時点で、待機列の先頭1人にだけ送る。診察中は送らない。
Web Push が許可されていなければ画面内表示へフォールバックし、どちらの場合も
送信記録を1件残す。記録の有無が二重送信の防止と画面表示の根拠になる。
"""

import logging

from django.db import IntegrityError, transaction

from notifier.models import NotificationLog, PushSubscription
from notifier.transport import get_transport
from queue_store.models import ConsultationRoomState
from queue_store.ordering import waiting_queue
from wait_time_engine import messages

logger = logging.getLogger(__name__)


def final_call_sent_to(entry):
    """この患者へ確定呼出を送信済みか。Status View の表示判定にも使う。"""
    return NotificationLog.objects.filter(
        entry=entry, kind=NotificationLog.Kind.FINAL_CALL
    ).exists()


def dispatch_final_call(now=None):
    """待機列の先頭へ確定呼出を送る。送れなかった場合は None を返す。"""
    if ConsultationRoomState.load().is_in_exam:
        # 手が空いていない間は送らない
        return None

    head = waiting_queue(now=now).first()
    if head is None:
        return None
    if final_call_sent_to(head):
        return None

    return _send_final_call(head)


def _send_final_call(entry):
    payload = {
        "title": "診察の順番になりました",
        "body": messages.FINAL_CALL,
        "url": f"/s/{entry.pk}/",
        "tag": f"final-call-{entry.pk}",
    }
    subscription = PushSubscription.objects.filter(entry=entry).order_by("-created_at").first()

    if subscription is None:
        # 未許可・未対応。画面内表示で伝える。
        return _log(entry, NotificationLog.Channel.IN_PAGE, detail="Web Push は未許可")

    delivered = False
    try:
        delivered = get_transport().send(subscription, payload)
    except Exception as error:  # 送信基盤の不調で呼び出しを止めない
        logger.warning("確定呼出の送信に失敗しました: %s", error)

    if delivered:
        return _log(entry, NotificationLog.Channel.WEB_PUSH)
    return _log(entry, NotificationLog.Channel.IN_PAGE, detail="Web Push の送信に失敗")


def _log(entry, channel, detail=""):
    try:
        with transaction.atomic():
            return NotificationLog.objects.create(
                entry=entry,
                kind=NotificationLog.Kind.FINAL_CALL,
                channel=channel,
                status=NotificationLog.Status.SENT,
                detail=detail,
            )
    except IntegrityError:
        # 同時実行で先に記録されていた場合は送信済みとして扱う
        return None
