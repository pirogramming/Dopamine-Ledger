# crew/forms.py
from django import forms
from .models import Crew

class CrewJoinForm(forms.Form):
    invite_code = forms.CharField(
        label='초대 코드',
        max_length=10,
        widget=forms.TextInput(attrs={'placeholder': '예: GR4BAO'}),
    )

    def clean_invite_code(self):
        # 입력값을 대문자로 통일 (소문자로 쳐도 찾아지게)
        return self.cleaned_data['invite_code'].strip().upper()

class CrewRenameForm(forms.ModelForm):
    class Meta:
        model = Crew
        fields = ['name']
        labels = {'name': '크루 이름'}
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': '새 크루 이름',
                'maxlength': 50,
            }),
        }

class CrewCreateForm(forms.ModelForm):
    target_hours = forms.IntegerField(
        label='목표 시간', min_value=1, initial=20,
        widget=forms.NumberInput(attrs={'placeholder': '20'}),
    )
    reward_text = forms.CharField(
        label='보상 문구', max_length=100, required=False,
        widget=forms.TextInput(attrs={'placeholder': '예: 목표 달성 시 크루 회식🍗'}),
    )

    class Meta:
        model = Crew
        fields = ['name']
        labels = {'name': '크루 이름'}
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '예: 새벽독서방', 'maxlength': 50}),
        }