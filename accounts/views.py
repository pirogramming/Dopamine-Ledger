import requests
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import render, redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import OnboardingSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .serializers import (
    UserLoginSerializer,
    UserRegisterSerializer,
    UserResponseSerializer,
)

User = get_user_model()


# ==========================================
# Template Render Views (페이지 화면 반환)
# ==========================================
@ensure_csrf_cookie
def signup_page(request):
  """회원가입 페이지 화면 반환 (@ensure_csrf_cookie: 첫 진입 시 csrftoken 쿠키 보장)"""
  return render(request, "accounts/signup.html")


@ensure_csrf_cookie
def login_page(request):
  """로그인 페이지 화면 반환 (@ensure_csrf_cookie: 첫 진입 시 csrftoken 쿠키 보장)"""
  return render(request, "accounts/login.html")

@ensure_csrf_cookie
def onboarding_page(request):
  if not request.user.is_authenticated:
        return redirect("login_page")
    
  if request.user.is_onboarded:
    return redirect("/ledger/")
        
  return render(request, "accounts/onboarding.html")


# ==========================================
# API Views (일반 로그인 / 회원가입 / 로그아웃)
# ==========================================
class SignupView(APIView):
  """회원가입 API"""

  permission_classes = [AllowAny]

  def post(self, request):
    serializer = UserRegisterSerializer(data=request.data)
    if serializer.is_valid():
      user = serializer.save()

      login(request, user, backend="django.contrib.auth.backends.ModelBackend")

      response_data = {
          "message": "회원가입이 완료되었습니다.",
          "user": UserResponseSerializer(user).data,
      }
      return Response(response_data, status=status.HTTP_201_CREATED)

    # 유효성 검사 실패 시
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
  """로그인 API"""
  authentication_classes = []
  permission_classes = [AllowAny]

  def post(self, request):
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
      user = serializer.validated_data["user"]

      login(request, user, backend="django.contrib.auth.backends.ModelBackend")

      response_data = {
          "message": "로그인에 성공하였습니다.",
          "user": UserResponseSerializer(user).data,
          "is_onboarded": user.is_onboarded
      }
      return Response(response_data, status=status.HTTP_200_OK)

    # 로그인 실패 시
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
  """로그아웃 API"""

  permission_classes = [IsAuthenticated]

  def post(self, request):
    # 세션 만료 및 쿠키 제거
    logout(request)
    return Response(
        {"message": "로그아웃되었습니다."}, status=status.HTTP_200_OK
    )


# ==========================================
# Kakao Social Login API
# ==========================================
class KakaoLoginRedirectView(APIView):
  permission_classes = [AllowAny]

  def get(self, request):
    url = (
      "https://kauth.kakao.com/oauth/authorize"
      f"?client_id={settings.KAKAO_REST_API_KEY}"
      f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
      "&response_type=code"
    )
    return redirect(url)
    
class KakaoCallbackView(APIView):
  """카카오 소셜 로그인 콜백 API"""

  permission_classes = [AllowAny]

  def get(self, request):
    # 1. 인가 코드 수신
    code = request.GET.get("code")
    if not code:
      return Response(
          {"error": "인가 코드가 전달되지 않았습니다."},
          status=status.HTTP_400_BAD_REQUEST,
      )

    # 2-1. 카카오 액세스 토큰 요청
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": getattr(settings, "KAKAO_REST_API_KEY", ""),
        "redirect_uri": getattr(settings, "KAKAO_REDIRECT_URI", ""),
        "code": code,
        "client_secret": getattr(settings, "KAKAO_CLIENT_SECRET", ""),
    }

    token_res = requests.post(
        token_url,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_json = token_res.json()

    access_token = token_json.get("access_token")
    if not access_token:
      return Response(
          {"error": "카카오 토큰 발급에 실패했습니다.", "details": token_json},
          status=status.HTTP_400_BAD_REQUEST,
      )

    # 2-2. 액세스 토큰으로 카카오 사용자 정보 요청
    user_info_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    user_info_res = requests.get(user_info_url, headers=headers)
    kakao_user_info = user_info_res.json()

    # 3. 사용자 정보 추출
    kakao_id = kakao_user_info.get("id")
    if not kakao_id:
      return Response(
          {"error": "카카오 사용자 정보를 가져오지 못했습니다."},
          status=status.HTTP_400_BAD_REQUEST,
      )

    kakao_account = kakao_user_info.get("kakao_account", {})
    email = kakao_account.get("email", f"kakao_{kakao_id}@example.com")
    nickname = kakao_account.get("profile", {}).get(
        "nickname", f"user_{kakao_id}"
    )

    # 4. DB에서 유저 조회 또는 생성 (계정 통합)
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": f"kakao_{kakao_id}",
            "nickname": nickname,
            "kakao_id": str(kakao_id),
        },
    )

    # 5. 세션 로그인 처리
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    return Response(
        {
            "message": "카카오 로그인 성공",
            "user": UserResponseSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


class OnboardingAPIView(APIView):
  permission_classes = [IsAuthenticated]

  def post(self, request):
    serializer = OnboardingSerializer(request.user, data=request.data, partial=True)

    if serializer.is_valid():
      serializer.save()

      request.user.is_onboarded = True
      request.user.save()

      return Response(
        {"message": "온보딩 정보가 성공적으로 저장되었습니다."},
        status=status.HTTP_200_OK
      )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
