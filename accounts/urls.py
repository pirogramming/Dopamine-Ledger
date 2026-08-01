from django.urls import path
from .views import SignupView, LoginView, signup_page, login_page

urlpatterns = [
    # HTML 페이지 경로
    path('signup-page/', signup_page, name="signup-page"),
    path('login-page/', login_page, name="login-page"),

    # 벡엔드 API 경로
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
]