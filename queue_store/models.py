"""Queue Store のモデル。

待機列（QueueEntry）、Duration Table（SymptomDuration）、営業時間（ClinicSchedule /
ClinicClosure）、診察中フラグ（ConsultationRoomState）、未登録症状アラートを保持する。
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from queue_store.fields import EncryptedTextField


def min_duration_minutes():
    """Duration Table の下限（分）。設定値が1未満でも1分を下回らない。"""
    return max(int(getattr(settings, "MIN_DURATION_MINUTES", 1)), 1)


def default_duration_minutes():
    """Duration Table に該当がない症状へ適用する既定の所要時間（分）。"""
    return max(int(getattr(settings, "DEFAULT_DURATION_MINUTES", 15)), min_duration_minutes())


class Weekday(models.IntegerChoices):
    MONDAY = 0, "月曜日"
    TUESDAY = 1, "火曜日"
    WEDNESDAY = 2, "水曜日"
    THURSDAY = 3, "木曜日"
    FRIDAY = 4, "金曜日"
    SATURDAY = 5, "土曜日"
    SUNDAY = 6, "日曜日"


class MasterBase(models.Model):
    """選択肢マスタの共通項目。並び順と有効・無効を運用側で変更できる。"""

    display_order = models.PositiveSmallIntegerField("表示順", default=0)
    is_active = models.BooleanField("有効", default=True)

    class Meta:
        abstract = True
        ordering = ["display_order", "pk"]


class AgeBand(MasterBase):
    label = models.CharField("年齢帯", max_length=20, unique=True)

    class Meta(MasterBase.Meta):
        verbose_name = "年齢帯"
        verbose_name_plural = "年齢帯"

    def __str__(self):
        return self.label


class Gender(MasterBase):
    code = models.SlugField("コード", max_length=20, unique=True)
    label = models.CharField("性別", max_length=20)

    class Meta(MasterBase.Meta):
        verbose_name = "性別"
        verbose_name_plural = "性別"

    def __str__(self):
        return self.label


class Symptom(MasterBase):
    code = models.SlugField("コード", max_length=40, unique=True)
    name = models.CharField("症状", max_length=60)

    class Meta(MasterBase.Meta):
        verbose_name = "症状"
        verbose_name_plural = "症状"

    def __str__(self):
        return self.name


class SymptomDuration(models.Model):
    """Duration Table。症状ごとの所要時間を実測値で更新していく。"""

    symptom = models.OneToOneField(
        Symptom, on_delete=models.CASCADE, related_name="duration", verbose_name="症状"
    )
    duration_minutes = models.PositiveIntegerField(
        "所要時間（分）", default=default_duration_minutes
    )
    sample_count = models.PositiveIntegerField("実測件数", default=0)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "所要時間（Duration Table）"
        verbose_name_plural = "所要時間（Duration Table）"
        ordering = ["symptom__display_order", "symptom__pk"]

    def __str__(self):
        return f"{self.symptom} / {self.duration_minutes}分"

    def clean(self):
        super().clean()
        minimum = min_duration_minutes()
        if self.duration_minutes is not None and self.duration_minutes < minimum:
            raise ValidationError(
                {"duration_minutes": f"所要時間は{minimum}分以上で登録してください。"}
            )

    def save(self, *args, **kwargs):
        self.duration_minutes = max(int(self.duration_minutes or 0), min_duration_minutes())
        super().save(*args, **kwargs)

    def record_actual(self, minutes):
        """実測値を取り込み、これまでの実測の平均として所要時間を更新する。"""
        measured = max(int(minutes), min_duration_minutes())
        total = self.duration_minutes * self.sample_count + measured
        self.sample_count += 1
        self.duration_minutes = round(total / self.sample_count)
        self.save(update_fields=["duration_minutes", "sample_count", "updated_at"])


class QueueEntry(models.Model):
    """待機列の1件。主キーがそのまま患者向けの一時識別子になる。"""

    class VisitType(models.TextChoices):
        RESERVED = "reserved", "予約"
        WALK_IN = "walk_in", "飛び込み"

    class Status(models.TextChoices):
        WAITING = "waiting", "待機中"
        IN_EXAM = "in_exam", "診察中"
        DONE = "done", "診察終了"

    id = models.UUIDField("一時識別子", primary_key=True, default=uuid.uuid4, editable=False)
    full_name = EncryptedTextField("氏名")
    kana = EncryptedTextField("フリガナ")
    age_band = models.ForeignKey(
        AgeBand, on_delete=models.PROTECT, related_name="entries", verbose_name="年齢帯"
    )
    gender = models.ForeignKey(
        Gender, on_delete=models.PROTECT, related_name="entries", verbose_name="性別"
    )
    symptom = models.ForeignKey(
        Symptom, on_delete=models.PROTECT, related_name="entries", verbose_name="症状"
    )
    free_text = EncryptedTextField("自由記述", blank=True, default="")
    visit_type = models.CharField("来院区分", max_length=16, choices=VisitType.choices)
    reserved_at = models.DateTimeField("予約時刻", null=True, blank=True)
    submitted_at = models.DateTimeField("問診票提出", default=timezone.now)
    status = models.CharField(
        "状態", max_length=16, choices=Status.choices, default=Status.WAITING
    )
    exam_started_at = models.DateTimeField("診察開始", null=True, blank=True)
    finished_at = models.DateTimeField("診察完了", null=True, blank=True)

    class Meta:
        verbose_name = "待機列のエントリ"
        verbose_name_plural = "待機列のエントリ"
        ordering = ["submitted_at"]
        indexes = [
            models.Index(fields=["status", "visit_type"], name="queue_status_visit_idx"),
            models.Index(fields=["reserved_at"], name="queue_reserved_at_idx"),
            models.Index(fields=["submitted_at"], name="queue_submitted_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(visit_type="walk_in")
                | models.Q(visit_type="reserved", reserved_at__isnull=False),
                name="reserved_visit_requires_reserved_at",
            )
        ]

    def __str__(self):
        return f"{self.full_name}（{self.get_visit_type_display()}）"

    @property
    def is_reserved(self):
        return self.visit_type == self.VisitType.RESERVED

    @property
    def queue_date(self):
        """待機列を当日分に絞るときの基準日（予約は予約時刻、飛び込みは提出時刻）。"""
        moment = self.reserved_at if self.is_reserved and self.reserved_at else self.submitted_at
        return timezone.localtime(moment).date()

    def clean(self):
        super().clean()
        if self.is_reserved and not self.reserved_at:
            raise ValidationError({"reserved_at": "予約来院では予約時刻が必要です。"})


class ConsultationRoomState(models.Model):
    """診察中フラグ。単一診察室・単一医師を前提とする。"""

    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    is_in_exam = models.BooleanField("診察中", default=False)
    current_entry = models.ForeignKey(
        QueueEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="診察中の患者",
    )
    started_at = models.DateTimeField("診察開始", null=True, blank=True)
    finished_at = models.DateTimeField("直近の診察完了", null=True, blank=True)

    class Meta:
        verbose_name = "診察室の状態"
        verbose_name_plural = "診察室の状態"

    def __str__(self):
        return "診察中" if self.is_in_exam else "空き"

    def save(self, *args, **kwargs):
        self.id = self.SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        state, _ = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return state


class ClinicSchedule(models.Model):
    """曜日ごとの受付時間。昼休みは受付を止めるが待ち時間の表示は続ける。"""

    weekday = models.PositiveSmallIntegerField("曜日", choices=Weekday.choices, unique=True)
    is_closed = models.BooleanField("休診日", default=False)
    open_time = models.TimeField("受付開始", null=True, blank=True)
    close_time = models.TimeField("受付終了", null=True, blank=True)
    break_start = models.TimeField("昼休み開始", null=True, blank=True)
    break_end = models.TimeField("昼休み終了", null=True, blank=True)

    class Meta:
        verbose_name = "受付時間"
        verbose_name_plural = "受付時間"
        ordering = ["weekday"]

    def __str__(self):
        label = Weekday(self.weekday).label
        if self.is_closed:
            return f"{label}: 休診"
        return f"{label}: {self.open_time:%H:%M}-{self.close_time:%H:%M}"

    def clean(self):
        super().clean()
        if self.is_closed:
            return
        if not self.open_time or not self.close_time:
            raise ValidationError("休診日以外は受付開始と受付終了を設定してください。")
        if self.open_time >= self.close_time:
            raise ValidationError({"close_time": "受付終了は受付開始より後にしてください。"})
        if bool(self.break_start) != bool(self.break_end):
            raise ValidationError("昼休みは開始と終了の両方を設定してください。")
        if self.break_start and not (
            self.open_time <= self.break_start < self.break_end <= self.close_time
        ):
            raise ValidationError({"break_start": "昼休みは受付時間内に収めてください。"})


class ClinicClosure(models.Model):
    """臨時休診日。曜日設定より優先する。"""

    date = models.DateField("休診日", unique=True)
    reason = models.CharField("理由", max_length=100, blank=True)

    class Meta:
        verbose_name = "臨時休診日"
        verbose_name_plural = "臨時休診日"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%Y-%m-%d} 休診"


class UnregisteredSymptomAlert(models.Model):
    """Duration Table に所要時間がない症状を検出した記録（運用者向けアラート）。"""

    symptom = models.ForeignKey(
        Symptom,
        on_delete=models.CASCADE,
        related_name="unregistered_alerts",
        verbose_name="症状",
    )
    entry = models.ForeignKey(
        QueueEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unregistered_alerts",
        verbose_name="対象の患者",
    )
    applied_minutes = models.PositiveIntegerField("適用した既定の所要時間（分）")
    created_at = models.DateTimeField("検出日時", auto_now_add=True)
    acknowledged = models.BooleanField("確認済み", default=False)
    acknowledged_at = models.DateTimeField("確認日時", null=True, blank=True)

    class Meta:
        verbose_name = "未登録症状アラート"
        verbose_name_plural = "未登録症状アラート"
        ordering = ["-created_at"]

    def __str__(self):
        return f"未登録症状: {self.symptom}"

    def acknowledge(self):
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["acknowledged", "acknowledged_at"])
