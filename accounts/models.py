from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField('이메일', max_length=255, unique=True)
    nickname = models.CharField('닉네임', max_length=30, unique=True)
    kakao_id = models.CharField('카카오 ID', max_length=100, blank=True, null=True)
    streak_days = models.IntegerField('연속 기록 일수', default=0)
    credit_grade = models.CharField('신용 등급', max_length=20, default='BRONZE')
    weekly_budget_min = models.DecimalField(
        '주간 예산(분)', max_digits=10, decimal_places=2, default=0
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'user'
        verbose_name = '사용자'
        verbose_name_plural = '사용자'

    def __str__(self):
        return self.nickname or self.email