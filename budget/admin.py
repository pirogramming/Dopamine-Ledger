from django.contrib import admin
from .models import Activity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('users', 'activity_type', 'rate')
    list_filter = ('activity_type',)
    search_fields = ('users__nickname', 'activity_type')