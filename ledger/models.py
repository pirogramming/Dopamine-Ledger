from django.conf import settings
from django.db import models


class SpendRecord(models.Model):
    users = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='spend_records'
    )
    spend_date = models.DateField('지출 날짜')
    category = models.CharField('카테고리', max_length=30)
    duration_min = models.IntegerField('지속 시간(분)')
    spend_start = models.DateTimeField('시작 시각')
    spend_end = models.DateTimeField('종료 시각')

    class Meta:
        db_table = 'spend_record'
        indexes = [models.Index(fields=['users', 'spend_date'])]


class EarnRecord(models.Model):
    users = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='earn_records'
    )
    activity = models.ForeignKey(
        'budget.Activity', on_delete=models.PROTECT,
        related_name='earn_records'
    )
    earn_min = models.DecimalField('적립 분', max_digits=8, decimal_places=2)
    verify_method = models.CharField('인증 방식', max_length=10)
    photo_url = models.TextField('인증 사진 URL', blank=True, null=True)
    earn_date = models.DateField('적립 날짜')
    earn_start = models.DateTimeField('시작 시각')
    earn_end = models.DateTimeField('종료 시각')

    class Meta:
        db_table = 'earn_record'
        indexes = [models.Index(fields=['users', 'earn_date'])]


class DailyClose(models.Model):
    users = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='daily_closes'
    )
    close_date = models.DateField('마감 날짜')
    closed_at = models.DateTimeField('마감 일시')

    class Meta:
        db_table = 'daily_close'
        unique_together = [['users', 'close_date']]