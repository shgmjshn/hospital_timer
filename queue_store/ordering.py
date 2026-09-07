"""待機列の並び順。

予約来院者を予約時刻順に先へ置き、飛び込み来院者を到着（提出）順で続ける。
対象は当日分のみで、予約は予約時刻の日付、飛び込みは提出時刻の日付で判定する。
"""

from django.db.models import Case, DateTimeField, F, IntegerField, Q, Value, When
from django.utils import timezone

from queue_store.models import QueueEntry

# 待機列に残る状態。診察中の患者も後続の待ち時間に算入するため含める。
ACTIVE_STATUSES = (QueueEntry.Status.WAITING, QueueEntry.Status.IN_EXAM)

RESERVED_PRIORITY = 0
WALK_IN_PRIORITY = 1


def waiting_queue(now=None):
    """当日の待機列を並び順どおりに返す。"""
    today = timezone.localdate(now or timezone.now())
    on_todays_queue = Q(
        visit_type=QueueEntry.VisitType.RESERVED, reserved_at__date=today
    ) | Q(visit_type=QueueEntry.VisitType.WALK_IN, submitted_at__date=today)

    return (
        QueueEntry.objects.filter(status__in=ACTIVE_STATUSES)
        .filter(on_todays_queue)
        .select_related("symptom", "symptom__duration")
        .annotate(
            visit_priority=Case(
                When(visit_type=QueueEntry.VisitType.RESERVED, then=Value(RESERVED_PRIORITY)),
                default=Value(WALK_IN_PRIORITY),
                output_field=IntegerField(),
            ),
            queue_key=Case(
                When(visit_type=QueueEntry.VisitType.RESERVED, then=F("reserved_at")),
                default=F("submitted_at"),
                output_field=DateTimeField(),
            ),
        )
        .order_by("visit_priority", "queue_key", "submitted_at", "pk")
    )


def position_of(entry, now=None):
    """待機列での順番（先頭が1）。待機列に無ければ None。"""
    for index, queued in enumerate(waiting_queue(now=now), start=1):
        if queued.pk == entry.pk:
            return index
    return None
