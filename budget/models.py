from django.conf import settings
from django.db import models


class Activity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField('활동 종류', max_length=30)
    rate = models.DecimalField('환산율', max_digits=3, decimal_places=2)

    class Meta:
        db_table = 'activity'

    def __str__(self):
        return f'{self.user} - {self.activity_type}'