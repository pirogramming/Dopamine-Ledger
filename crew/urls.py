# crew/urls.py
from django.urls import path

from . import views

app_name = 'crew'

urlpatterns = [
    path('', views.crew_list, name='list'),
    path('create/', views.crew_create, name='create'),
    path('join/', views.crew_join, name='join'),
    path('join/<str:invite_code>/', views.crew_join_by_link, name='join_by_link'),
    path('<int:crew_id>/', views.crew_detail, name='detail'),
    path('<int:crew_id>/leave/', views.crew_leave, name='leave'),
    path('<int:crew_id>/members/', views.crew_members_api, name='members_api'),
    path('<int:crew_id>/manage/', views.crew_manage, name='manage'),
    path('<int:crew_id>/kick/<int:member_id>/', views.crew_kick, name='kick'),
    path('<int:crew_id>/member/<int:member_id>/', views.crew_member_detail, name='member_detail'),
]