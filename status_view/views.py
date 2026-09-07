"""患者向けの表示画面。

一時識別リンクから開く単一画面と、待合室のモニタ向けの総合表示。どちらも
ログインや登録を要求しない。値はキャッシュせず、開くたびに算出し直す。
"""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from queue_store.models import QueueEntry
from wait_time_engine import engine


def _private(response):
    """一時識別リンクの内容をキャッシュ・インデックスさせない。"""
    response["Cache-Control"] = "no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def status_detail(request, token):
    entry = get_object_or_404(QueueEntry, pk=token)
    status = engine.status_for(entry)
    return _private(
        render(request, "status_view/detail.html", {"entry": entry, "status": status})
    )


def status_state(request, token):
    """ポーリング用の状態。症状と自由記述は含めない。"""
    entry = get_object_or_404(QueueEntry, pk=token)
    status = engine.status_for(entry)
    return _private(
        JsonResponse(
            {
                "phase": status.phase.value,
                "wait_text": status.wait_text,
                "message": status.message,
                "position": status.position,
                "waiting_count": status.waiting_count,
                "poll_interval_seconds": settings.STATUS_POLL_INTERVAL_SECONDS,
                "final_call": status.final_call,
            }
        )
    )


def lobby(request):
    status = engine.overall_status()
    return _private(render(request, "status_view/lobby.html", {"status": status}))


def lobby_state(request):
    status = engine.overall_status()
    return _private(
        JsonResponse(
            {
                "phase": status.phase.value,
                "wait_text": status.wait_text,
                "message": status.message,
                "waiting_count": status.waiting_count,
                "poll_interval_seconds": settings.STATUS_POLL_INTERVAL_SECONDS,
            }
        )
    )
