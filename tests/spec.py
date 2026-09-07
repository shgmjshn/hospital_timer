"""仕様が定める定数と時刻ヘルパー。テストと conftest から共有する。"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# 全テストの基準時刻: 2026-09-02(水) 10:00 JST。診療時間内かつ昼休み前。
FROZEN_NOW = "2026-09-02 10:00:00+09:00"
AFTER_CLOSING = "2026-09-02 20:00:00+09:00"
DURING_LUNCH_BREAK = "2026-09-02 12:45:00+09:00"

OPEN_TIME = time(9, 0)
CLOSE_TIME = time(18, 0)
BREAK_START = time(12, 30)
BREAK_END = time(13, 30)

# 仕様が定める表示文言
MSG_CLOSED = "本日の受付は終了しました"
MSG_NO_WAITING = "お待ちの方はいません"
MSG_READY_NOW = "すぐにご案内できます"
MSG_COME_TO_ROOM = "まもなくお呼びします"
MSG_FINAL_CALL = "診察室にお入りください"
MSG_FINISHED = "診察は終了しました"

# 待ち時間表示の必須フォーマット
WAIT_TEXT_PATTERN = r"^約[0-9]+分$"
WAIT_TEXT_IN_PAGE_PATTERN = r"約[0-9]+分"


def jst(year, month, day, hour, minute=0):
    """JST の aware な datetime を返す。"""
    return datetime(year, month, day, hour, minute, tzinfo=JST)
