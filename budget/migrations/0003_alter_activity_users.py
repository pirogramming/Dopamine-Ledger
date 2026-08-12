# budget/migrations/0003_alter_activity_users.py
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('budget', '0002_alter_activity_rate'),   # 최신 budget 마이그레이션 이름으로
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='users',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='activities',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]