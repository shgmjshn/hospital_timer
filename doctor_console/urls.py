from django.contrib.auth import views as auth_views
from django.urls import path

from doctor_console import views
from doctor_console.forms import DoctorLoginForm

app_name = "doctor_console"

urlpatterns = [
    path("", views.queue, name="queue"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="doctor_console/login.html",
            authentication_form=DoctorLoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("entry/<uuid:token>/", views.entry_detail, name="entry_detail"),
    path("entry/<uuid:token>/start/", views.start_exam, name="start_exam"),
    path("entry/<uuid:token>/finish/", views.finish_exam, name="finish_exam"),
]
