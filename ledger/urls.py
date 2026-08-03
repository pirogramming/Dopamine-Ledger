from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'ledger'  # 템플릿에서 {% url 'ledger:xxx' %}로 부르려면 이 줄 필수

urlpatterns = [
        # 메인 화면 (홈)
    path('', TemplateView.as_view(template_name='ledger/main_progress.html'), name='main_progress'),
    path('convert/', TemplateView.as_view(template_name='ledger/main_convert.html'), name='main_convert'),



    # 기록하기 진입 화면 (지출/수입 선택)
    path('record/', TemplateView.as_view(template_name='ledger/record_choice.html'), name='record_choice'),

    # 지출 기록
    path('record/spend/', TemplateView.as_view(template_name='ledger/spend_record_create.html'), name='spend_record_create'),
    path('spend/', TemplateView.as_view(template_name='ledger/spend_record_list.html'), name='spend_record_list'),

    # 수입 기록
    path('record/earn/', views.earn_record_create, name='earn_record_create'),
    path('earn/', views.earn_record_list, name='earn_record_list'),
]