from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Users


@admin.register(Users)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'nickname', 'streak_days', 'credit_grade', 'is_staff')
    search_fields = ('email', 'nickname')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('추가 정보', {
            'fields': ('nickname', 'kakao_id', 'streak_days',
                       'credit_grade', 'weekly_budget_min')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('추가 정보', {
            'fields': ('email', 'nickname')
        }),
    )