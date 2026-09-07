"""待ち時間の算出。

待ち時間は「対象患者より前に並ぶ患者の所要時間の合計」で、表示は `約N分` に限る。
待ち時間を出さない場面は `Phase` で区別し、案内文を `message` に載せる。
"""

from dataclasses import dataclass
from enum import StrEnum

from django.utils import timezone

from queue_store import hours
from queue_store.models import (
    QueueEntry,
    SymptomDuration,
    UnregisteredSymptomAlert,
    default_duration_minutes,
    min_duration_minutes,
)
from queue_store.ordering import waiting_queue
from wait_time_engine import messages


class Phase(StrEnum):
    """患者の画面に何を出すかの区分。"""

    WAITING = "waiting"
    COME_TO_ROOM = "come_to_room"
    IN_EXAM = "in_exam"
    FINISHED = "finished"
    CLOSED = "closed"
    SCHEDULED_FUTURE = "scheduled_future"
    QUEUE_EMPTY = "queue_empty"


# 状況が変わりうる区分。これ以外はポーリングしても内容が変わらない。
LIVE_PHASES = frozenset({Phase.WAITING, Phase.COME_TO_ROOM, Phase.IN_EXAM})


@dataclass(frozen=True)
class PatientStatus:
    phase: Phase
    wait_text: str | None
    message: str | None
    position: int | None
    waiting_count: int
    final_call: bool = False

    @property
    def should_poll(self):
        return self.phase in LIVE_PHASES


@dataclass(frozen=True)
class OverallStatus:
    phase: Phase
    wait_text: str | None
    message: str | None
    waiting_count: int


def format_minutes(minutes):
    """待ち時間の表示文字列。範囲表現を使わず、必ず「約」と「分」を付ける。"""
    return f"約{max(int(minutes), 0)}分"


def duration_minutes_for(symptom, entry=None):
    """症状の所要時間。Duration Table に無ければ既定値を適用しアラートを記録する。"""
    try:
        return max(symptom.duration.duration_minutes, min_duration_minutes())
    except SymptomDuration.DoesNotExist:
        applied = default_duration_minutes()
        UnregisteredSymptomAlert.objects.get_or_create(
            symptom=symptom, entry=entry, defaults={"applied_minutes": applied}
        )
        return applied


def wait_minutes_for(entry, now=None):
    """対象患者より前に並ぶ患者の所要時間の合計。待機列に無ければ0。"""
    queue = list(waiting_queue(now=now))
    # 未登録症状は待機列の全員分を検出したいので、先に全件の所要時間を求める
    minutes_by_id = {queued.pk: duration_minutes_for(queued.symptom, entry=queued) for queued in queue}

    total = 0
    for queued in queue:
        if queued.pk == entry.pk:
            return total
        total += minutes_by_id[queued.pk]
    return 0


def recalculate(now=None):
    """待機列全体の所要時間を求め直す。問診票の提出時に呼ぶ。

    待ち時間は読み出しのたびに計算しキャッシュしないため、ここでの再計算は
    未登録症状の検出とアラート記録を提出の時点で確定させる意味を持つ。
    """
    return {
        queued.pk: duration_minutes_for(queued.symptom, entry=queued)
        for queued in waiting_queue(now=now)
    }


def status_for(entry, now=None):
    """患者1人分の表示内容。"""
    moment = now or timezone.now()
    queue = list(waiting_queue(now=moment))
    waiting_count = len(queue)

    if entry.status == QueueEntry.Status.DONE:
        return PatientStatus(Phase.FINISHED, None, messages.FINISHED, None, waiting_count)

    if _is_future_reservation(entry, moment):
        return PatientStatus(
            Phase.SCHEDULED_FUTURE,
            None,
            messages.scheduled_future(entry.reserved_at),
            None,
            waiting_count,
        )

    position = next(
        (index for index, queued in enumerate(queue, start=1) if queued.pk == entry.pk), None
    )
    if position is None:
        # 当日の待機列から外れたエントリ。一時識別リンクの有効期間は終わっている。
        return PatientStatus(Phase.FINISHED, None, messages.FINISHED, None, waiting_count)

    if not hours.is_open(moment):
        return PatientStatus(
            Phase.CLOSED, None, messages.closed(hours.next_open_at(moment)), None, waiting_count
        )

    if entry.status == QueueEntry.Status.IN_EXAM:
        return PatientStatus(Phase.IN_EXAM, None, messages.IN_EXAM, position, waiting_count)

    if _has_final_call(entry):
        # イベントB: 確定呼出は事前案内より優先する
        return PatientStatus(
            Phase.COME_TO_ROOM,
            None,
            messages.FINAL_CALL,
            position,
            waiting_count,
            final_call=True,
        )

    minutes = wait_minutes_for(entry, now=moment)
    if minutes == 0:
        # イベントA: 待ち時間が0に到達した患者への事前案内
        return PatientStatus(
            Phase.COME_TO_ROOM, None, messages.COME_TO_ROOM, position, waiting_count
        )

    return PatientStatus(Phase.WAITING, format_minutes(minutes), None, position, waiting_count)


def overall_status(now=None):
    """待合室向けの総合表示。待機列が空のときは待ち時間を出さない。"""
    moment = now or timezone.now()

    if not hours.is_open(moment):
        return OverallStatus(
            Phase.CLOSED, None, messages.closed(hours.next_open_at(moment)), 0
        )

    queue = list(waiting_queue(now=moment))
    if not queue:
        return OverallStatus(Phase.QUEUE_EMPTY, None, messages.QUEUE_EMPTY, 0)

    total = sum(duration_minutes_for(queued.symptom, entry=queued) for queued in queue)
    return OverallStatus(Phase.WAITING, format_minutes(total), None, len(queue))


def reception_closed_message(now=None):
    """受付を止めている理由の案内。昼休みと営業時間外で文言を分ける。"""
    moment = now or timezone.now()
    reopen_at = hours.next_open_at(moment)
    if hours.is_open(moment):
        return messages.reception_paused(reopen_at)
    return messages.closed(reopen_at)


def _has_final_call(entry):
    """確定呼出を送信済みか。送信の有無は Notifier の記録を唯一の根拠とする。"""
    from notifier.dispatcher import final_call_sent_to

    return final_call_sent_to(entry)


def _is_future_reservation(entry, now):
    if not entry.is_reserved or not entry.reserved_at:
        return False
    return entry.queue_date > timezone.localdate(now)
