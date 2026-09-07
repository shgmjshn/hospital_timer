"""受付時間の判定。

営業時間内（`is_open`）と受付可能（`is_reception_open`）を区別する。昼休みは
受付を止めるが待ち時間の表示は続けるため、前者には昼休みを含める。
"""

from datetime import datetime, timedelta

from django.utils import timezone

from queue_store.models import ClinicClosure, ClinicSchedule

# 次回受付時刻を探す日数の上限
SEARCH_DAYS = 14


def _localtime(now=None):
    return timezone.localtime(now or timezone.now())


def _schedule_for(date):
    """その日に受付がある場合のみ受付時間を返す。休診日は None。"""
    if ClinicClosure.objects.filter(date=date).exists():
        return None
    schedule = ClinicSchedule.objects.filter(weekday=date.weekday()).first()
    if schedule is None or schedule.is_closed:
        return None
    if not schedule.open_time or not schedule.close_time:
        return None
    return schedule


def _combine(date, at_time):
    return timezone.make_aware(datetime.combine(date, at_time))


def schedule_of_day(now=None):
    return _schedule_for(_localtime(now).date())


def is_open(now=None):
    """営業時間内か。昼休みを含む。待ち時間を表示してよいかの判定に使う。"""
    local = _localtime(now)
    schedule = _schedule_for(local.date())
    if schedule is None:
        return False
    return schedule.open_time <= local.time() < schedule.close_time


def is_on_break(now=None):
    """昼休み中か。"""
    local = _localtime(now)
    schedule = _schedule_for(local.date())
    if schedule is None or not schedule.break_start or not schedule.break_end:
        return False
    return schedule.break_start <= local.time() < schedule.break_end


def is_reception_open(now=None):
    """問診票を受け付けてよいか。営業時間内かつ昼休み外。"""
    local = _localtime(now)
    return is_open(local) and not is_on_break(local)


def next_open_at(now=None):
    """次に受付が開く時刻。すでに受付中ならその時刻自身を返す。"""
    local = _localtime(now)
    if is_reception_open(local):
        return local

    schedule = _schedule_for(local.date())
    if schedule is not None:
        reopen_times = [schedule.open_time]
        if schedule.break_end:
            reopen_times.append(schedule.break_end)
        for reopen_time in sorted(reopen_times):
            if local.time() < reopen_time:
                return _combine(local.date(), reopen_time)

    for offset in range(1, SEARCH_DAYS + 1):
        date = local.date() + timedelta(days=offset)
        schedule = _schedule_for(date)
        if schedule is not None:
            return _combine(date, schedule.open_time)
    return None
