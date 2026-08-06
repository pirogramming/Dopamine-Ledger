from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'ledger'

urlpatterns = [
    # 메인 화면 (홈) — 아직 뷰 없이 정적이라 TemplateView 유지 OK
    path('', TemplateView.as_view(template_name='ledger/main_progress.html'), name='main_progress'),
    path('convert/', TemplateView.as_view(template_name='ledger/main_convert.html'), name='main_convert'),

    # 기록하기 진입 화면 (정적이라 TemplateView OK)
    path('record/', TemplateView.as_view(template_name='ledger/record_choice.html'), name='record_choice'),

    # 지출 기록 — 실제 뷰로 되돌림 (TemplateView면 저장 안 됨)
    path('record/spend/', views.spend_record_create, name='spend_record_create'),
    path('spend/', views.spend_record_list, name='spend_record_list'),

    # 수입 기록
    path('record/earn/', views.earn_record_create, name='earn_record_create'),
    path('earn/', views.earn_record_list, name='earn_record_list'),

    # 하루 마감
    path('daily-close/', views.daily_close, name='daily_close'),
]