"""通知許可の登録。

Status View で患者がブラウザの通知を許可したときに、その届け先を保存する。
連絡先は受け取らず、保存するのは一時識別子とブラウザ発行の購読情報だけ。
"""

import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from notifier.models import PushSubscription
from queue_store.models import QueueEntry


@require_POST
def subscribe(request, token):
    entry = get_object_or_404(QueueEntry, pk=token)
    if entry.status == QueueEntry.Status.DONE:
        # 診察が終わった一時識別子は届け先として受け付けない
        raise Http404

    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "不正な形式です。"}, status=400)

    endpoint = payload.get("endpoint") or ""
    keys = payload.get("keys") or {}
    p256dh = keys.get("p256dh") or ""
    auth = keys.get("auth") or ""
    if not (endpoint and p256dh and auth):
        return JsonResponse({"error": "購読情報が足りません。"}, status=400)

    subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"entry": entry, "p256dh": p256dh, "auth": auth},
    )
    return JsonResponse({"subscribed": True}, status=201 if created else 200)
