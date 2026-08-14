from django.contrib.auth.models import AbstractUser
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator


class Users(AbstractUser):
    email = models.EmailField('이메일', max_length=255, unique=True)
    nickname = models.CharField('닉네임', max_length=30, unique=True)
    streak_days = models.IntegerField('연속 기록 일수', default=0)
    credit_grade = models.CharField('신용 등급', max_length=20, default='BRONZE')
    weekly_budget_min = models.DecimalField(
        '주간 예산(분)', max_digits=10, decimal_places=2, default=210
    )
    kakao_id = models.CharField('카카오 ID', max_length=100, blank=True, null=True)
    kakao_access_token = models.CharField('카카오 액세스 토큰', max_length=255, blank=True, null=True)
    kakao_refresh_token = models.CharField('카카오 리프레시 토큰', max_length=255, blank=True, null=True)
    
    converting_activity = models.CharField('환산활동', max_length=100, blank=True, null=True)
    conversion_base = models.DecimalField(
        '환산 기준(분)', max_digits=12, decimal_places=6, default=Decimal('360'),
        validators=[
            MinValueValidator(Decimal('0.000001'), message='값이 올바르지 않습니다.'),
        ],
        help_text='선택한 단위 1개를 얻는 데 필요한 분. 예: 책 1권=360, 운동 1회=40. 환산 = (분 ÷ 이 값)'
    )
    conversion_unit = models.CharField('환산단위', max_length=30, blank=True, null=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='accounts_users_set',
        blank=True,
        verbose_name='groups',
        help_text='The groups this user belongs to.',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='accounts_users_set',
        blank=True,
        verbose_name='user permissions',
        help_text='Specific permissions for this user.',
    )

    is_onboarded = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        verbose_name = '사용자'
        verbose_name_plural = '사용자'

    def __str__(self):
        return self.nickname or self.email