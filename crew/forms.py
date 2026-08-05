# crew/forms.py
from django import forms

from .models import Crew


class CrewCreateForm(forms.ModelForm):
    class Meta:
        model = Crew
        fields = ['name']          # 크루명만 입력받는다
        labels = {'name': '크루 이름'}
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': '예: 도파민 파티 크루',
                'maxlength': 50,
            }),
        }

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