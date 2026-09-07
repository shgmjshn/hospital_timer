from django.urls import path

from intake import views

app_name = "intake"

urlpatterns = [
    path("", views.IntakeFormView.as_view(), name="form"),
]
