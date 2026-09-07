"""患者向けの表示文言。

待ち時間そのものは `engine.format_minutes` が作る `約N分` に限る。ここに置くのは
待ち時間を表示しない場面（閉院・待機列が空・呼び出し・診察終了）の案内文。
"""

from django.utils import timezone
from django.utils.dateformat import format as format_datetime

QUEUE_EMPTY = "お待ちの方はいません。すぐにご案内できます。"
COME_TO_ROOM = "まもなくお呼びします。診察室の前にお越しください。"
# イベントBはイベントAの案内を上書きするため、事前案内の言い回しを含めて一文にする
FINAL_CALL = "順番になりました。まもなくお呼びしますので、診察室にお入りください。"
IN_EXAM = "ただ今診察中です。"
FINISHED = "診察は終了しました。お大事にどうぞ。"


def _japanese_datetime(value):
    return format_datetime(timezone.localtime(value), "n月j日 H:i")


def closed(next_open_at=None):
    """営業時間外・休診日の案内。"""
    if next_open_at is None:
        return "本日の受付は終了しました。"
    return f"本日の受付は終了しました。次回受付時刻は{_japanese_datetime(next_open_at)}です。"


def reception_paused(reopen_at=None):
    """昼休みなどで受付を止めている間の案内。待ち時間の表示は続ける。"""
    if reopen_at is None:
        return "ただ今受付を休止しています。"
    return f"ただ今受付を休止しています。受付再開は{_japanese_datetime(reopen_at)}です。"


def scheduled_future(reserved_at):
    """予約日が当日でない患者への案内。"""
    return (
        f"ご予約は{_japanese_datetime(reserved_at)}です。"
        "当日になると待ち時間が表示されます。"
    )
