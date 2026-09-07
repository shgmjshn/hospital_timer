"""初期マスタ（年齢帯・性別・症状・Duration Table・受付時間）を投入する。

何度実行しても同じ結果になり、Duration Table に蓄積された実測値は上書きしない。
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from queue_store.models import AgeBand, ClinicSchedule, Gender, Symptom, SymptomDuration, Weekday

AGE_BANDS = [
    "0〜5歳",
    "6〜15歳",
    "16〜39歳",
    "40〜64歳",
    "65〜74歳",
    "75歳以上",
]

GENDERS = [
    ("male", "男性"),
    ("female", "女性"),
    ("other", "その他"),
    ("undisclosed", "回答しない"),
]

# (コード, 症状名, 既定の所要時間（分）)
SYMPTOMS = [
    ("fever", "発熱", 15),
    ("cough_throat", "咳・のどの痛み", 10),
    ("stomach", "腹痛・下痢", 20),
    ("headache", "頭痛", 15),
    ("rash", "皮膚のかゆみ・湿疹", 10),
    ("injury", "けが・打撲", 20),
    ("lifestyle", "血圧・生活習慣病の相談", 15),
    ("vaccination", "予防接種", 10),
    ("checkup", "健康診断・書類の相談", 20),
    ("other", "その他", 15),
]

# (曜日, 受付開始, 受付終了, 昼休み開始, 昼休み終了)
SCHEDULES = [
    (Weekday.MONDAY, time(9, 0), time(18, 0), time(12, 30), time(14, 0)),
    (Weekday.TUESDAY, time(9, 0), time(18, 0), time(12, 30), time(14, 0)),
    (Weekday.WEDNESDAY, time(9, 0), time(12, 30), None, None),
    (Weekday.THURSDAY, time(9, 0), time(18, 0), time(12, 30), time(14, 0)),
    (Weekday.FRIDAY, time(9, 0), time(18, 0), time(12, 30), time(14, 0)),
    (Weekday.SATURDAY, time(9, 0), time(13, 0), None, None),
]


class Command(BaseCommand):
    help = "問診票の選択肢・Duration Table・受付時間の初期値を投入する"

    @transaction.atomic
    def handle(self, *args, **options):
        for order, label in enumerate(AGE_BANDS, start=1):
            AgeBand.objects.update_or_create(label=label, defaults={"display_order": order})

        for order, (code, label) in enumerate(GENDERS, start=1):
            Gender.objects.update_or_create(
                code=code, defaults={"label": label, "display_order": order}
            )

        for order, (code, name, minutes) in enumerate(SYMPTOMS, start=1):
            symptom, _ = Symptom.objects.update_or_create(
                code=code, defaults={"name": name, "display_order": order}
            )
            SymptomDuration.objects.get_or_create(
                symptom=symptom, defaults={"duration_minutes": minutes}
            )

        for weekday, open_time, close_time, break_start, break_end in SCHEDULES:
            ClinicSchedule.objects.update_or_create(
                weekday=weekday,
                defaults={
                    "is_closed": False,
                    "open_time": open_time,
                    "close_time": close_time,
                    "break_start": break_start,
                    "break_end": break_end,
                },
            )
        ClinicSchedule.objects.update_or_create(
            weekday=Weekday.SUNDAY,
            defaults={
                "is_closed": True,
                "open_time": None,
                "close_time": None,
                "break_start": None,
                "break_end": None,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"初期マスタを投入しました: 年齢帯{AgeBand.objects.count()}件 / "
                f"性別{Gender.objects.count()}件 / 症状{Symptom.objects.count()}件 / "
                f"受付時間{ClinicSchedule.objects.count()}件"
            )
        )
