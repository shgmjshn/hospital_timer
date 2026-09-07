"""運用者アカウントを環境変数から用意する。

Render の無料枠にはシェルがないため、起動時に管理者兼医師を作れるようにする。
既にあるユーザーはパスワードを上書きしない（再デプロイで意図せず変わらないように）。
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "DJANGO_SUPERUSER_* が設定されていれば、管理者兼医師を用意する"

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.clinic").strip()
        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME / PASSWORD が無いので、ユーザー作成は飛ばします。")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email, "is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"運用者 {username} を作成しました。"))
        else:
            changed = False
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                changed = True
            if email and user.email != email:
                user.email = email
                changed = True
            if changed:
                user.save()
            self.stdout.write(f"運用者 {username} は既にあります。")

        group, _ = Group.objects.get_or_create(name=settings.DOCTOR_GROUP_NAME)
        user.groups.add(group)
