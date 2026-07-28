from django.conf import settings
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator


class Activity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField('활동 종류', max_length=30)
    rate = models.DecimalField(
        '환산율', max_digits=3, decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal('0.01'),
                message='값이 올바르지 않습니다.'
            ),
            MaxValueValidator(
                Decimal('0.99'),
                message='값이 올바르지 않습니다.'
            ),
        ]
    )



    class Meta:
        db_table = 'activity'
        constraints = [
            models.CheckConstraint(
                check=models.Q(rate__gt=0) & models.Q(rate__lt=1),
                name='rate_between_0_and_1',
            )
        ]

    def __str__(self):
        return f'{self.user} - {self.activity_type}'