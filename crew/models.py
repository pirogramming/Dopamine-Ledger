from django.conf import settings
from django.db import models


class Crew(models.Model):
    name = models.CharField('크루명', max_length=50)
    invite_code = models.CharField('초대 코드', max_length=10, unique=True)
    status = models.CharField('상태', max_length=10, default='WAITING')

    class Meta:
        db_table = 'crew'

    def __str__(self):
        return self.name


class CrewMember(models.Model):
    crew = models.ForeignKey(
        Crew, on_delete=models.CASCADE, related_name='members'
    )
    users = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crew_memberships'
    )
    joined_date = models.DateField('가입일', auto_now_add=True)

    class Meta:
        db_table = 'crew_member'
        unique_together = [['crew', 'users']]