"""通知の購読と送信記録。

連絡先（電話・メール）は集めない。届け先はブラウザが発行する Web Push の購読情報だけで、
それも一時識別子に紐づく。許可されていない患者には画面内表示で伝える。
"""

from django.db import models


class PushSubscription(models.Model):
    """患者のブラウザが発行した Web Push の届け先。"""

    entry = models.ForeignKey(
        "queue_store.QueueEntry",
        verbose_name="対象患者",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField("エンドポイント", max_length=500, unique=True)
    p256dh = models.CharField("公開鍵", max_length=255)
    auth = models.CharField("認証シークレット", max_length=255)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)

    class Meta:
        verbose_name = "プッシュ購読"
        verbose_name_plural = "プッシュ購読"
        indexes = [models.Index(fields=["entry"])]

    def __str__(self):
        return f"{self.entry_id} の購読"


class NotificationLog(models.Model):
    """送信した通知の記録。二重送信の判定にも使う。"""

    class Kind(models.TextChoices):
        FINAL_CALL = "final_call", "確定呼出"

    class Channel(models.TextChoices):
        WEB_PUSH = "web_push", "Web Push"
        IN_PAGE = "in_page", "画面内表示"

    class Status(models.TextChoices):
        SENT = "sent", "送信済み"
        FAILED = "failed", "送信失敗"

    entry = models.ForeignKey(
        "queue_store.QueueEntry",
        verbose_name="対象患者",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField("種別", max_length=20, choices=Kind.choices)
    channel = models.CharField("経路", max_length=20, choices=Channel.choices)
    status = models.CharField(
        "結果", max_length=20, choices=Status.choices, default=Status.SENT
    )
    detail = models.CharField("補足", max_length=200, blank=True)
    created_at = models.DateTimeField("送信日時", auto_now_add=True)

    class Meta:
        verbose_name = "通知記録"
        verbose_name_plural = "通知記録"
        ordering = ["created_at"]
        constraints = [
            # 同じ患者へ同じ種別の通知を二重に送らない
            models.UniqueConstraint(fields=["entry", "kind"], name="unique_notification_per_entry"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} / {self.get_channel_display()}"
