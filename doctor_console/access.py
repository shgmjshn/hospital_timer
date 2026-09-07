"""医師ロールに限定するアクセス制御。

未ログインはログイン画面へ誘導し、ログイン済みでも医師ロールがなければ 403 で返す。
症状・自由記述はこの関門より内側でしか描画しない。
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from queue_store.permissions import is_doctor


def doctor_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not is_doctor(request.user):
            raise PermissionDenied("症状・自由記述の閲覧には医師ロールが必要です。")
        return view(request, *args, **kwargs)

    return _wrapped
