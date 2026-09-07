from django.apps import AppConfig


class QueueStoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "queue_store"
    verbose_name = "待機列ストア"
