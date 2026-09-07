from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from config.views import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("intake/", include("intake.urls")),
    path("doctor/", include("doctor_console.urls")),
    # サービスワーカーはサイト全体を担当させるため、ルート直下から配る
    path(
        "sw.js",
        TemplateView.as_view(template_name="sw.js", content_type="text/javascript"),
        name="service_worker",
    ),
    path("", include("notifier.urls")),
    path("", include("status_view.urls")),
]
