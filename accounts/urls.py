from django.urls import path
from .views import (
    signup_page,
    login_page,
    onboarding_page,
    settings_page,
    profile_edit,
    account_delete,
    password_change,
    budget_edit,
    rate_edit,
    unit_edit,
    SignupView,
    LoginView,
    LogoutView,
    KakaoLoginRedirectView,
    KakaoCallbackView,
    OnboardingAPIView,
)

urlpatterns = [
    # HTML 페이지 경로
    path('signup-page/', signup_page, name="signup-page"),
    path('login-page/', login_page, name="login-page"),
    path('onboarding-page/', onboarding_page, name="onboarding-page"),
    path('settings-page/', settings_page, name="settings-page"),

    # 벡엔드 API 경로
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('onboarding/', OnboardingAPIView.as_view(), name='onboarding'),

    # 카카오 소셜 로그인 콜백
    path('kakao/login/', KakaoLoginRedirectView.as_view(), name='kakao_login'),
    path('kakao/callback/', KakaoCallbackView.as_view(), name='kakao_callback'),

    # 설정 기능 경로
    path('profile-edit/', profile_edit, name='profile-edit'),
    path('account-delete/', account_delete, name='account-delete'),
    path('password-change/', password_change, name='password-change'),

    path('budget-edit/', budget_edit, name='budget-edit'),
    path('rate-edit/', rate_edit, name='rate-edit'),
    path('unit-edit/', unit_edit, name='unit-edit'),
]