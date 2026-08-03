from django import forms
from django.utils import timezone
from .models import SpendRecord, EarnRecord
from budget.models import Activity
from budget.services import calculate_earn_minutes   # 환산 로직 단일화

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
        ('short_form', '숏폼'),
    ]
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        label='카테고리',
        initial='short_form',
    )
    
    class Meta:
        model = SpendRecord
        # spend_date, spend_start, spend_end는 폼에 노출하지 않고 save()에서 자동 채움
        fields = ['category']
    
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
        
        cleaned_data['duration_min']=total_minutes
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
        instance.spend_date = now.date()
        
        if commit:
            instance.save()
        return instance

class EarnRecordForm(forms.ModelForm):
    """
    와이어프레임(수입기록-타이머 / 수입기록-수동입력 / 수입 종료 후 적립) 기준 폼
    
    -activity: 로그인한 유저가 등록한 활동 중에서만 선택 가능 ( 다른 유저 활동 노출 금지)
    -입력 방식은 2가지이고 사용자가 직접 고르는 게 아니라 "어느 화면으로 들어왔는지"로 결정됨
        1) 타이머: 실제 시작~종료 시각을 그대로 받음
        2) 수동입력: 시:분만 입력받고 now()기준으로 역산
    -earn_min(적립 분) = 활동 시간(분) x activity.rate -> 폼 저장 시 자동 계산 (사용자가 직접 입력 X)
    """
    ENTRY_MODE_CHOICES = [
        ('timer', '타이머'),
        ('manual', '수동입력'),
    ]
    
    #view가 어느 화면(타이머/수동입력)에서 왔는지 알려주는 값. 사용자에게 직접 노출되지 않음
    entry_mode = forms.ChoiceField(choices=ENTRY_MODE_CHOICES, widget=forms.HiddenInput)
    
    #수동 입력일 때만 사용
    hours = forms.IntegerField(label='시간', min_value=0, max_value=23, required=False, initial=0)
    minutes = forms.IntegerField(label='분', min_value=0, max_value=59, required=False, initial=0)

    #타이머일 때만 사용
    timer_start = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    timer_end = forms.DateTimeField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = EarnRecord
        #activity, photo_url만 모델 필드에서 직접 노출
        # earn_min/verify_method/earn_date/earn_start/earn_end는 save()에서 자동 계산해서 채움
        fields = ['activity', 'photo_url']
        widgets = {
            'photo_url': forms.URLInput(attrs={'placeholder': '인증 사진 URL (선택)'}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        """
        activity 선택지를 현재 로그인한 유저 소유 활동으로 제한.
        view에서 반드시 user를 넘겨줘야 함: EarnRecordForm(data=..., user=request.user)
        """
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['activity'].queryset = Activity.objects.filter(users=user)
        else:
            # user 없이 생성되면 실수로 전체 유저 활동이 노출될 위험이 있어 방어적으로 빈 쿼리셋 처리
            self.fields['activity'].queryset = Activity.objects.none()
    
    def clean(self):
        """
        entry_mode에 따라 duration_min을 계산하는 지점만 분기
        - manual: hours/minutes 합산 (0분이면 에러 — SpendRecordForm과 동일한 원칙)
        - timer: timer_start/timer_end 차이 계산 (end <= start면 에러)
        """
        
        cleaned_data = super().clean()
        entry_mode = cleaned_data.get('entry_mode')

        if entry_mode == 'manual':
            hours = cleaned_data.get('hours') or 0
            minutes = cleaned_data.get('minutes') or 0
            total_minutes = hours * 60 + minutes
            if total_minutes <= 0:
                raise forms.ValidationError('활동 시간은 0분보다 커야 합니다.')
            cleaned_data['duration_min'] = total_minutes

        elif entry_mode == 'timer':
            start = cleaned_data.get('timer_start')
            end = cleaned_data.get('timer_end')
            if not start or not end:
                raise forms.ValidationError('타이머 시작/종료 시각이 누락되었습니다.')
            if end <= start:
                raise forms.ValidationError('종료 시각은 시작 시각보다 늦어야 합니다.')
            duration = (end - start).total_seconds() / 60
            cleaned_data['duration_min'] = round(duration)

        else:
            raise forms.ValidationError('입력 방식(entry_mode)이 올바르지 않습니다.')

        return cleaned_data
    
    def save(self, commit=True):
        """
        - earn_start/earn_end/earn_date: entry_mode가 timer면 실제 타이머 시각, manual이면 now() 역산
        - earn_min: 공용환산함수(calculate_earn_minutes)로 계산
        - verify_method: entry_mode 값을 그대로 저장 → 사용자가 고르지 않고 진입 경로로 자동 결정
            (와이어프레임 "수입 종료 후 적립" 화면 주석: "타이머/수동 중 실제 입력 경로에 따라 기본 선택")
        """
        instance = super().save(commit=False)

        entry_mode = self.cleaned_data['entry_mode']
        duration_min = self.cleaned_data['duration_min']
        activity = self.cleaned_data['activity']

        if entry_mode == 'timer':
            instance.earn_start = self.cleaned_data['timer_start']
            instance.earn_end = self.cleaned_data['timer_end']
        else:  # manual일 때
            now = timezone.now()
            instance.earn_end = now
            instance.earn_start = now - timezone.timedelta(minutes=duration_min)

        instance.earn_date = instance.earn_end.date()
        instance.verify_method = entry_mode
        
        # 적립분 계산은 공용 환산 함수로 단일화 (budget/services.py)
        instance.earn_min = calculate_earn_minutes(duration_min, activity.rate)
        
        if commit:
            instance.save()
        return instance

    def clean_photo_url(self):
        """인증 사진은 선택 사항(nullable). 값이 있으면 앞뒤 공백만 방어적으로 제거."""
        url = self.cleaned_data.get('photo_url', '')
        return url.strip() if url else url