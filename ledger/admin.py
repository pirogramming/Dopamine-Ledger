from django.contrib import admin
from .models import SpendRecord, EarnRecord, DailyClose


@admin.register(SpendRecord)
class SpendRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'spend_date', 'category', 'duration_min')
    list_filter = ('category', 'spend_date')
    search_fields = ('user__nickname',)


@admin.register(EarnRecord)
class EarnRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'earn_date', 'activity', 'earn_min', 'verify_method')
    list_filter = ('earn_date', 'verify_method')
    search_fields = ('user__nickname',)


@admin.register(DailyClose)
class DailyCloseAdmin(admin.ModelAdmin):
    list_display = ('user', 'close_date', 'closed_at')
    list_filter = ('close_date',)