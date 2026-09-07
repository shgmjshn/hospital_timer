"""テンプレート全体で使う表示設定。

可読性の数値基準（本文・待ち時間の文字サイズ）とポーリング間隔は設定値を
唯一の情報源とし、CSS カスタムプロパティとして描画する。
"""

from django.conf import settings


def display(request):
    return {
        "clinic_name": settings.CLINIC_NAME,
        "body_font_size_px": settings.STATUS_VIEW_MIN_BODY_FONT_PX,
        "wait_font_size_px": settings.STATUS_VIEW_WAIT_FONT_PX,
        "poll_interval_seconds": settings.STATUS_POLL_INTERVAL_SECONDS,
        "vapid_public_key": settings.VAPID_PUBLIC_KEY,
    }
