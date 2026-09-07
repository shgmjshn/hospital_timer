"""問診票フォーム。

氏名・フリガナ・年齢・性別・症状は必須。自由記述は任意で、症状を選ばずに
記入することはできない。来院区分が予約のときだけ予約時刻を必須にする。
"""

from django import forms

from queue_store import hours
from queue_store.models import AgeBand, Gender, QueueEntry, Symptom

RESERVED_AT_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
]


class IntakeForm(forms.ModelForm):
    full_name = forms.CharField(
        label="氏名",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "name"}),
    )
    kana = forms.CharField(
        label="フリガナ",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )
    age_band = forms.ModelChoiceField(
        label="年齢",
        queryset=AgeBand.objects.filter(is_active=True),
        empty_label="選択してください",
        widget=forms.Select(attrs={"class": "input"}),
    )
    gender = forms.ModelChoiceField(
        label="性別",
        queryset=Gender.objects.filter(is_active=True),
        empty_label=None,
        widget=forms.RadioSelect,
    )
    symptom = forms.ModelChoiceField(
        label="症状",
        queryset=Symptom.objects.filter(is_active=True),
        empty_label="選択してください",
        widget=forms.Select(attrs={"class": "input"}),
    )
    visit_type = forms.ChoiceField(
        label="来院区分",
        choices=QueueEntry.VisitType.choices,
        widget=forms.RadioSelect,
    )
    reserved_at = forms.DateTimeField(
        label="予約時刻",
        required=False,
        input_formats=RESERVED_AT_INPUT_FORMATS,
        widget=forms.DateTimeInput(
            attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )
    free_text = forms.CharField(
        label="そのほか伝えたいこと",
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 4}),
    )

    class Meta:
        model = QueueEntry
        fields = [
            "full_name",
            "kana",
            "age_band",
            "gender",
            "symptom",
            "free_text",
            "visit_type",
            "reserved_at",
        ]

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("free_text") and not cleaned.get("symptom"):
            self.add_error("free_text", "症状を選んでから記入してください。")

        if cleaned.get("visit_type") == QueueEntry.VisitType.RESERVED:
            reserved_at = cleaned.get("reserved_at")
            if not reserved_at:
                self.add_error("reserved_at", "予約来院の場合は予約時刻を入力してください。")
            elif not hours.is_reception_open(reserved_at):
                self.add_error("reserved_at", "予約時刻は受付時間内で指定してください。")
        else:
            cleaned["reserved_at"] = None

        return cleaned
