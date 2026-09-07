"""通知の運用確認用の管理画面。

記録は運用の証跡なので追加・編集はさせず、閲覧だけにする。
"""

from django.contrib import admin

from notifier.models import NotificationLog, PushSubscription


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entry", "kind", "channel", "status", "detail")
    list_filter = ("kind", "channel", "status")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entry", "endpoint")
    search_fields = ("endpoint",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
