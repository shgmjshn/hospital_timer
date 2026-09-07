from django.contrib import admin
from django.utils import timezone

from queue_store.models import (
    AgeBand,
    ClinicClosure,
    ClinicSchedule,
    ConsultationRoomState,
    Gender,
    QueueEntry,
    Symptom,
    SymptomDuration,
    UnregisteredSymptomAlert,
)
from queue_store.permissions import is_doctor


class MasterAdmin(admin.ModelAdmin):
    list_display = ["__str__", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active"]


@admin.register(AgeBand)
class AgeBandAdmin(MasterAdmin):
    pass


@admin.register(Gender)
class GenderAdmin(MasterAdmin):
    list_display = ["label", "code", "display_order", "is_active"]


@admin.register(Symptom)
class SymptomAdmin(MasterAdmin):
    list_display = ["name", "code", "registered_duration", "display_order", "is_active"]
    search_fields = ["name", "code"]

    @admin.display(description="所要時間")
    def registered_duration(self, obj):
        duration = getattr(obj, "duration", None)
        return f"{duration.duration_minutes}分" if duration else "未登録"


@admin.register(SymptomDuration)
class SymptomDurationAdmin(admin.ModelAdmin):
    list_display = ["symptom", "duration_minutes", "sample_count", "updated_at"]
    list_editable = ["duration_minutes"]
    list_select_related = ["symptom"]
    readonly_fields = ["sample_count", "updated_at"]


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    """症状と自由記述は医師ロールにのみ表示する。"""

    list_display = ["short_id", "full_name", "visit_type", "status", "reserved_at", "submitted_at"]
    list_filter = ["status", "visit_type"]
    date_hierarchy = "submitted_at"

    NON_CLINICAL_FIELDS = [
        "id",
        "full_name",
        "kana",
        "age_band",
        "gender",
        "visit_type",
        "reserved_at",
        "submitted_at",
        "status",
        "exam_started_at",
        "finished_at",
    ]

    @admin.display(description="一時識別子")
    def short_id(self, obj):
        return str(obj.pk)[:8]

    def get_fields(self, request, obj=None):
        fields = list(self.NON_CLINICAL_FIELDS)
        if is_doctor(request.user):
            fields.insert(fields.index("gender") + 1, "symptom")
            fields.append("free_text")
        return fields

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    def has_add_permission(self, request):
        return False


@admin.register(ConsultationRoomState)
class ConsultationRoomStateAdmin(admin.ModelAdmin):
    list_display = ["__str__", "is_in_exam", "current_entry", "started_at", "finished_at"]

    def has_add_permission(self, request):
        return ConsultationRoomState.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ClinicSchedule)
class ClinicScheduleAdmin(admin.ModelAdmin):
    list_display = ["weekday", "is_closed", "open_time", "close_time", "break_start", "break_end"]
    list_editable = ["is_closed", "open_time", "close_time", "break_start", "break_end"]


@admin.register(ClinicClosure)
class ClinicClosureAdmin(admin.ModelAdmin):
    list_display = ["date", "reason"]


@admin.register(UnregisteredSymptomAlert)
class UnregisteredSymptomAlertAdmin(admin.ModelAdmin):
    list_display = ["symptom", "applied_minutes", "created_at", "acknowledged", "acknowledged_at"]
    list_filter = ["acknowledged", "symptom"]
    readonly_fields = ["symptom", "entry", "applied_minutes", "created_at", "acknowledged_at"]
    actions = ["mark_acknowledged"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="選択したアラートを確認済みにする")
    def mark_acknowledged(self, request, queryset):
        updated = queryset.filter(acknowledged=False).update(
            acknowledged=True, acknowledged_at=timezone.now()
        )
        self.message_user(request, f"{updated}件を確認済みにしました。")
