from django.urls import path

from notifier import views

app_name = "notifier"

urlpatterns = [
    path("s/<uuid:token>/subscribe", views.subscribe, name="subscribe"),
]
