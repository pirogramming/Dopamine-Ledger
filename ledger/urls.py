from django.urls import path
from . import views

app_name = 'ledger'  # 템플릿에서 {% url 'ledger:xxx' %}로 부르려면 이 줄 필수

urlpatterns = [
    # 기록하기 진입 화면 (지출/수입 선택)
    path('record/', views.record_choice, name='record_choice'),

    # 지출 기록
    path('record/spend/', views.spend_record_create, name='spend_record_create'),
    path('spend/', views.spend_record_list, name='spend_record_list'),

    # 수입 기록
    path('record/earn/', views.earn_record_create, name='earn_record_create'),
    path('earn/', views.earn_record_list, name='earn_record_list'),
]