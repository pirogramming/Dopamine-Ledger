from django.contrib import admin
from .models import Crew, CrewMember, FeedEvent


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ('name', 'invite_code', 'status')
    search_fields = ('name', 'invite_code')


@admin.register(CrewMember)
class CrewMemberAdmin(admin.ModelAdmin):
    list_display = ('crew', 'users', 'joined_date')
    list_filter = ('joined_date',)


@admin.register(FeedEvent)
class FeedEventAdmin(admin.ModelAdmin):
    list_display = ('crew', 'event_type', 'actor', 'target', 'message', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('crew__name', 'message')