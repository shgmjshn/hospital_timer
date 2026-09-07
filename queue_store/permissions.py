"""症状・自由記述を閲覧できる医師ロールの判定。"""

from django.conf import settings


def is_doctor(user):
    """医師ロールを持つか。管理者は運用のため同等に扱う。"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=settings.DOCTOR_GROUP_NAME).exists()
