"""診察の状態変化を伝えるシグナル。

Notifier はこの `exam_finished` を受けて確定呼出（イベントB）を送る。
Queue Store から Notifier を直接呼ばないことで、依存の向きを一方向に保つ。
"""

from django.dispatch import Signal

# entry: QueueEntry
exam_started = Signal()
exam_finished = Signal()
