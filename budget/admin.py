from django.contrib import admin
from .models import Activity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'rate')
    list_filter = ('activity_type',)
    search_fields = ('user__nickname', 'activity_type')