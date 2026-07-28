from django.contrib import admin
from .models import Crew, CrewMember


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ('name', 'invite_code', 'status')
    search_fields = ('name', 'invite_code')


@admin.register(CrewMember)
class CrewMemberAdmin(admin.ModelAdmin):
    list_display = ('crew', 'user', 'joined_date')
    list_filter = ('joined_date',)