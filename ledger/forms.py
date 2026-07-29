from django import forms
from django.utils import timezone
from .models import SpendRecord

class SpendRecordForm(forms.ModelForm):
    # 00:30처럼 시:분을 따로 입력받기 위해 별도 필드 두 개 사용
    hours = forms.IntegerField(
        label='시간', min_value=0, max_value=23, initial=0
    )
    minutes = forms.IntegerField(
        label='분', min_value=0, max_value=59, initial=0
    )
    
    # MVP 단계라 카테고리는 숏폼하나로 고정
    # 나중에 SNS, 게임, 기타 추가할 때 이 리스트만 늘리면 됨
    CATEGORY_CHOICES = [
        ('숏폼', '숏폼'),
    ]
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        label='카테로리',
        initial='숏폼',
    )
    
    class Meta:
        model = SpendRecord
        # spend_date, spend_start, spend_end는 폼에 노출하지 않고 save()에서 자동 채움
        fields = []
    
    def clean(self):
        """
        hours/minutes를 합쳐서 duration_min을 계산
        총 0분은 지출기록으로 의미가 없으니 error 처리함
        """
        cleaned_data = super().clean()
        hours = cleaned_data.get('hours') or 0
        minutes = cleaned_data.get('minutes') or 0
        
        total_minutes = hours * 60 + minutes
        if total_minutes <= 0:
            raise forms.ValidationError('지출 시간은 0분보다 커야 합니다.')
        
        cleaned_data['durations_min']=total_minutes
        return cleaned_data
    
    def save(self, commit=True):
        """
        -duration_min: clean()에서 계산한 값
        -spend_end: 저장 시점(now) = "방금 끝난 활동"이라고 가정
        -spend_start: spend_end에서 duration만큼 뺀 시각(역산)
        -spend_date: spend_end의 날짜
        
        * 과거 날짜 기록을 지원하지 않는 이유:
            하루 마감은 "해당 날짜에 기록이 있어야 인정"되는 구조라 지난 날짜 기록을
            나중에 추가해도 그날의 마감 조건은 이미 리셋된 뒤라 의미가 없음
            -> 항상 "지금 막 끝난 활동"만 기록하는 것으로 설계
        """
        instance = super().save(commit=False)
        
        duration_min = self.cleaned_data['duration_min']
        now = timezone.now()
        
        instance.duration_min = duration_min
        instance.spend_end = now
        instance.spend_start = now - timezone.timedelta(minutes=duration_min)
        instance.spend_data = now.date()
        
        if commit:
            instance.save()
        return instance
        