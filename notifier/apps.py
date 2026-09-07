from django.apps import AppConfig


class NotifierConfig(AppConfig):
    name = "notifier"
    verbose_name = "Notifier（通知ディスパッチャー）"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from notifier import receivers  # noqa: F401  シグナル受信の登録
