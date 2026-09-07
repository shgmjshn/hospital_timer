"""受入テスト共通のフィクスチャ。

アプリ側の実装モジュールはフィクスチャやテストの内部で遅延インポートしている。
未実装の段階でもテストの収集が成立し、失敗理由が個々のテストに現れるようにするため。
"""

import itertools
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from freezegun import freeze_time

from tests.spec import (
    BREAK_END,
    BREAK_START,
    CLOSE_TIME,
    FROZEN_NOW,
    OPEN_TIME,
    jst,
)


@pytest.fixture(autouse=True)
def frozen_now():
    """時刻依存の判定を固定する。個別テストは with freeze_time(...) で上書きする。"""
    with freeze_time(FROZEN_NOW) as frozen:
        yield frozen


@pytest.fixture
def clinic_hours(db):
    """毎日 9:00-18:00（昼休み 12:30-13:30）で開院している営業時間マスタ。"""
    from queue_store.models import ClinicSchedule

    schedules = []
    for weekday in range(7):
        schedule, _ = ClinicSchedule.objects.update_or_create(
            weekday=weekday,
            defaults={
                "is_closed": False,
                "open_time": OPEN_TIME,
                "close_time": CLOSE_TIME,
                "break_start": BREAK_START,
                "break_end": BREAK_END,
            },
        )
        schedules.append(schedule)
    return schedules


@pytest.fixture
def masters(db):
    """年齢帯・性別・症状と Duration Table の初期マスタ。

    unregistered は Duration Table に所要時間を持たない症状（未登録症状の検証用）。
    """
    from queue_store.models import AgeBand, Gender, Symptom, SymptomDuration

    age_band = AgeBand.objects.create(label="16〜64歳", display_order=3)
    age_band_child = AgeBand.objects.create(label="0〜5歳", display_order=1)
    gender_female = Gender.objects.create(code="female", label="女性", display_order=2)
    gender_male = Gender.objects.create(code="male", label="男性", display_order=1)

    fever = Symptom.objects.create(code="fever", name="発熱", display_order=1)
    SymptomDuration.objects.create(symptom=fever, duration_minutes=10)
    stomach = Symptom.objects.create(code="stomach", name="腹痛", display_order=2)
    SymptomDuration.objects.create(symptom=stomach, duration_minutes=20)
    rash = Symptom.objects.create(code="rash", name="皮膚のかゆみ", display_order=3)
    SymptomDuration.objects.create(symptom=rash, duration_minutes=8)
    unregistered = Symptom.objects.create(code="other", name="その他", display_order=99)

    return SimpleNamespace(
        age_band=age_band,
        age_band_child=age_band_child,
        gender=gender_female,
        gender_male=gender_male,
        fever=fever,
        stomach=stomach,
        rash=rash,
        unregistered=unregistered,
    )


@pytest.fixture
def make_entry(db, masters):
    """待機列のエントリを作る。提出時刻は呼び出し順に 1 秒ずつずらす。"""
    from queue_store.models import QueueEntry

    counter = itertools.count(1)

    def _make(
        symptom=None,
        *,
        visit_type=None,
        reserved_at=None,
        submitted_at=None,
        full_name="山田 太郎",
        kana="ヤマダ タロウ",
        free_text="",
        status=None,
    ):
        order = next(counter)
        return QueueEntry.objects.create(
            full_name=full_name,
            kana=kana,
            age_band=masters.age_band,
            gender=masters.gender,
            symptom=symptom or masters.fever,
            free_text=free_text,
            visit_type=visit_type or QueueEntry.VisitType.WALK_IN,
            reserved_at=reserved_at,
            submitted_at=submitted_at or (jst(2026, 9, 2, 9, 0) + timedelta(seconds=order)),
            status=status or QueueEntry.Status.WAITING,
        )

    return _make


@pytest.fixture
def intake_payload(masters):
    """Intake Form の妥当な POST データを返す。値に None を渡すと項目自体を送らない。"""
    from queue_store.models import QueueEntry

    def _payload(**overrides):
        payload = {
            "full_name": "佐藤 花子",
            "kana": "サトウ ハナコ",
            "age_band": str(masters.age_band.pk),
            "gender": str(masters.gender.pk),
            "symptom": str(masters.fever.pk),
            "visit_type": QueueEntry.VisitType.WALK_IN,
            "free_text": "",
        }
        payload.update(overrides)
        return {key: value for key, value in payload.items() if value is not None}

    return _payload


@pytest.fixture
def room(db):
    """診察中フラグ（単一診察室）。"""
    from queue_store.models import ConsultationRoomState

    return ConsultationRoomState.load()


@pytest.fixture
def doctor(db, settings):
    """医師ロールを持つユーザー。"""
    user = get_user_model().objects.create_user(
        username="doctor1", password="acceptance-test-doctor", is_staff=True
    )
    group, _ = Group.objects.get_or_create(name=settings.DOCTOR_GROUP_NAME)
    user.groups.add(group)
    return user


@pytest.fixture
def non_doctor(db):
    """医師ロールを持たないログインユーザー（受付職員など）。"""
    return get_user_model().objects.create_user(
        username="staff1", password="acceptance-test-staff"
    )


@pytest.fixture
def doctor_client(client, doctor):
    client.force_login(doctor)
    return client


@pytest.fixture
def non_doctor_client(non_doctor):
    client = Client()
    client.force_login(non_doctor)
    return client


@pytest.fixture
def fresh_client():
    """Cookie もキャッシュも持たない未認証クライアント。"""
    return Client()


@pytest.fixture
def push_transport(settings):
    """Web Push の送信をメモリ上に記録するトランスポートへ差し替える。"""
    from notifier.transport import MemoryTransport

    settings.NOTIFIER_PUSH_TRANSPORT = "notifier.transport.MemoryTransport"
    MemoryTransport.reset()
    yield MemoryTransport
    MemoryTransport.reset()


@pytest.fixture
def make_push_subscription(db):
    """患者が Web Push を許可した状態を作る。"""

    def _make(entry, endpoint=None):
        from notifier.models import PushSubscription

        return PushSubscription.objects.create(
            entry=entry,
            endpoint=endpoint or f"https://push.example.test/{entry.pk}",
            p256dh="acceptance-test-p256dh",
            auth="acceptance-test-auth",
        )

    return _make
