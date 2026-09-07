"""診察開始・診察完了の記録。

完了時は待機列から外し、診察中フラグを下げてから `exam_finished` を送る。
Notifier はこのシグナルを受けて次の患者へ確定呼出を送る。
"""

from django.db import transaction
from django.utils import timezone

from queue_store.models import ConsultationRoomState, QueueEntry, SymptomDuration
from queue_store.signals import exam_finished, exam_started

# これ未満で完了した記録は誤操作とみなし、Duration Table の実測値に反映しない
MIN_MEASURABLE_SECONDS = 60


class ExamStateError(RuntimeError):
    """診察開始・完了の記録が現在の診察室の状態と矛盾する。"""


@transaction.atomic
def start_exam(entry, now=None):
    """診察開始を記録し、診察中フラグを立てる。"""
    moment = now or timezone.now()
    state = ConsultationRoomState.load()
    if state.is_in_exam and state.current_entry_id and state.current_entry_id != entry.pk:
        raise ExamStateError("すでに別の患者の診察中です。")

    entry.status = QueueEntry.Status.IN_EXAM
    entry.exam_started_at = moment
    entry.save(update_fields=["status", "exam_started_at"])

    state.is_in_exam = True
    state.current_entry = entry
    state.started_at = moment
    state.save(update_fields=["is_in_exam", "current_entry", "started_at"])

    exam_started.send(sender=start_exam, entry=entry)
    return entry


@transaction.atomic
def finish_exam(entry=None, now=None):
    """診察完了を記録し、待機列から外して診察中フラグを下げる。"""
    moment = now or timezone.now()
    state = ConsultationRoomState.load()
    target = entry or state.current_entry
    if target is None:
        raise ExamStateError("診察中の患者がいません。")

    target.status = QueueEntry.Status.DONE
    target.finished_at = moment
    target.save(update_fields=["status", "finished_at"])
    _record_measured_duration(target)

    state.is_in_exam = False
    state.current_entry = None
    state.finished_at = moment
    state.save(update_fields=["is_in_exam", "current_entry", "finished_at"])

    exam_finished.send(sender=finish_exam, entry=target)
    return target


def _record_measured_duration(entry):
    """実際にかかった時間を Duration Table に取り込む。"""
    if not entry.exam_started_at or not entry.finished_at:
        return
    elapsed = (entry.finished_at - entry.exam_started_at).total_seconds()
    if elapsed < MIN_MEASURABLE_SECONDS:
        return
    duration = SymptomDuration.objects.filter(symptom=entry.symptom).first()
    if duration is None:
        return
    duration.record_actual(round(elapsed / 60))
