from django.contrib.auth.forms import AuthenticationForm


class DoctorLoginForm(AuthenticationForm):
    """見た目を共通レイアウトに合わせただけの認証フォーム。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "input", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "input", "autocomplete": "current-password"}
        )
