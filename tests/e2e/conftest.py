"""E2E 用のフィクスチャ。

実ブラウザから触るため、上位 conftest の時刻固定を無効にする。freezegun は
`time.monotonic` まで止めるため、Playwright のタイムアウト計測が壊れる。
代わりに営業時間を終日開院にし、待機列は実時刻で組み立てて、いつ実行しても同じ結果になるようにする。
"""

import itertools
import os
import time as time_module
from datetime import time, timedelta

import pytest
from django.utils import timezone

# Playwright の同期 API はスレッド内でイベントループを回すため、Django の
# 非同期セーフ検査に引っかかる。ブラウザ操作の間は呼び出し側が待ち合わせるので、
# 実際に並行実行されることはない。
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

@pytest.fixture(scope="session")
def browser_type_launch_args(pytestconfig):
    """Playwright 同梱の Chromium は WSL2 で起動直後に SIGSEGV することがある。

    指定がなければシステムの Google Chrome を使う。
    上書きは `pytest -m e2e --browser-channel chromium`。
    """
    launch_options = {
        "channel": pytestconfig.getoption("--browser-channel") or "chrome",
        "args": ["--disable-gpu", "--disable-dev-shm-usage"],
    }
    if pytestconfig.getoption("--headed"):
        launch_options["headless"] = False
    slowmo = pytestconfig.getoption("--slowmo")
    if slowmo:
        launch_options["slow_mo"] = slowmo
    return launch_options


@pytest.fixture(autouse=True)
def frozen_now():
    """時刻固定を E2E では行わない（上位 conftest の autouse を上書きする）。"""
    yield None


@pytest.fixture
def clinic_hours(db):
    """終日開院・昼休みなし。実行時刻に関係なく受付中にするため。"""
    from queue_store.models import ClinicSchedule

    for weekday in range(7):
        ClinicSchedule.objects.update_or_create(
            weekday=weekday,
            defaults={
                "is_closed": False,
                "open_time": time(0, 0),
                "close_time": time(23, 59),
                "break_start": None,
                "break_end": None,
            },
        )


@pytest.fixture
def make_entry(db, masters):
    """実時刻で待機列のエントリを作る。提出時刻は呼び出し順に 1 秒ずつずらす。"""
    from queue_store.models import QueueEntry

    counter = itertools.count(1)
    base = timezone.now() - timedelta(minutes=10)

    def _make(symptom=None, *, full_name="山田 太郎", free_text="", **overrides):
        order = next(counter)
        return QueueEntry.objects.create(
            full_name=full_name,
            kana="ヤマダ タロウ",
            age_band=masters.age_band,
            gender=masters.gender,
            symptom=symptom or masters.fever,
            free_text=free_text,
            visit_type=QueueEntry.VisitType.WALK_IN,
            submitted_at=base + timedelta(seconds=order),
            status=QueueEntry.Status.WAITING,
            **overrides,
        )

    return _make


@pytest.fixture
def wait_until():
    """ブラウザ側の非同期処理の結果がデータベースに現れるまで待つ。"""

    def _wait(predicate, timeout=10.0, interval=0.2):
        deadline = time_module.monotonic() + timeout
        while time_module.monotonic() < deadline:
            if predicate():
                return True
            time_module.sleep(interval)
        return False

    return _wait
