from django.urls import path

from status_view import views

app_name = "status_view"

urlpatterns = [
    path("", views.lobby, name="lobby"),
    path("state.json", views.lobby_state, name="lobby_state"),
    path("s/<uuid:token>/", views.status_detail, name="detail"),
    path("s/<uuid:token>/state.json", views.status_state, name="state"),
]
