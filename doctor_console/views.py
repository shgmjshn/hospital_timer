"""医師向けの待機列と診察の記録。

症状・自由記述を扱うのはこの画面だけで、いずれも医師ロールを確認したうえで描画する。
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from doctor_console.access import doctor_required
from queue_store import hours, services
from queue_store.models import ConsultationRoomState, QueueEntry
from queue_store.ordering import waiting_queue
from wait_time_engine import engine


@doctor_required
def queue(request):
    room = ConsultationRoomState.load()
    entries = list(waiting_queue())
    return render(
        request,
        "doctor_console/queue.html",
        {
            "entries": entries,
            "room": room,
            "reception_open": hours.is_reception_open(),
            "overall": engine.overall_status(),
        },
    )


@doctor_required
def entry_detail(request, token):
    entry = get_object_or_404(QueueEntry, pk=token)
    return render(
        request,
        "doctor_console/entry_detail.html",
        {
            "entry": entry,
            "room": ConsultationRoomState.load(),
            "duration_minutes": engine.duration_minutes_for(entry.symptom, entry=entry),
        },
    )


@doctor_required
@require_POST
def start_exam(request, token):
    entry = get_object_or_404(QueueEntry, pk=token)
    try:
        services.start_exam(entry)
    except services.ExamStateError as error:
        messages.error(request, str(error))
    return redirect("doctor_console:queue")


@doctor_required
@require_POST
def finish_exam(request, token):
    entry = get_object_or_404(QueueEntry, pk=token)
    try:
        services.finish_exam(entry)
    except services.ExamStateError as error:
        messages.error(request, str(error))
    return redirect("doctor_console:queue")
