"""問診票の入力と提出。

受付停止中（営業時間外・休診日・昼休み）は入力画面を出さず、提出も受け付けない。
提出が通ると Queue Store へ登録し、UUID v4 の一時識別リンクへ送る。
"""

from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from intake.forms import IntakeForm
from queue_store import hours
from wait_time_engine import engine


class IntakeFormView(FormView):
    template_name = "intake/form.html"
    form_class = IntakeForm

    def dispatch(self, request, *args, **kwargs):
        if not hours.is_reception_open():
            return render(
                request,
                "intake/closed.html",
                {"message": engine.reception_closed_message()},
                status=403 if request.method == "POST" else 200,
            )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        entry = form.save()
        engine.recalculate()
        return redirect("status_view:detail", token=entry.pk)
