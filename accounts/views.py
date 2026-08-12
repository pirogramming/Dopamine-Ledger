import requests
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import render, redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import OnboardingSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash

from budget.models import Activity
from decimal import Decimal

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
        return redirect("login-page")
    
  if request.user.is_onboarded:
    return redirect("/ledger/")
        
  return render(request, "accounts/onboarding.html")

@login_required
def settings_page(request):
    """설정 메인 화면."""
    return render(request, 'accounts/settings.html', {
        'active_tab': 'setting',
    })

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
            "nickname": f"kakao_{kakao_id}",
            "kakao_id": str(kakao_id),
        },
    )

    # 4-1. 토큰 저장 (기존 유저도 갱신)
    refresh_token = token_json.get("refresh_token")
    user.kakao_id = str(kakao_id)
    user.kakao_access_token = access_token
    if refresh_token:
        user.kakao_refresh_token = refresh_token
    user.save(update_fields=['kakao_id', 'kakao_access_token', 'kakao_refresh_token'])

    # 5. 세션 로그인
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    # 6. 온보딩 여부에 따라 분기
    if user.is_onboarded:
        return redirect('/ledger/')
    return redirect('onboarding-page')

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

# ==========================================
# 설정 (개인정보 수정、 계정 탈퇴 및 비밀번호 변경)
# ==========================================

@login_required
def profile_edit(request):
    """개인정보 수정: 닉네임/이메일."""
    user = request.user

    if request.method == 'POST':
        nickname = request.POST.get('nickname', '').strip()
        email = request.POST.get('email', '').strip()

        # 중복 체크 (본인 제외)
        if User.objects.filter(nickname=nickname).exclude(id=user.id).exists():
            messages.error(request, '이미 사용 중인 닉네임이에요.')
        elif User.objects.filter(email=email).exclude(id=user.id).exists():
            messages.error(request, '이미 사용 중인 이메일이에요.')
        elif not nickname or not email:
            messages.error(request, '닉네임과 이메일을 모두 입력해주세요.')
        else:
            user.nickname = nickname
            user.email = email
            user.save(update_fields=['nickname', 'email'])
            messages.success(request, '저장했어요.')
            return redirect('profile-edit')

    return render(request, 'accounts/profile_edit.html', {
        'active_tab': 'setting',
    })


@login_required
def account_delete(request):
    """계정 탈퇴."""
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('login-page')
    return redirect('profile-edit')

@login_required
def password_change(request):
    """비밀번호 변경: 현재 비번 확인 → 새 비번 검증 → 변경."""
    user = request.user

    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password1', '')
        new2 = request.POST.get('new_password2', '')

        if not user.check_password(current):
            messages.error(request, '현재 비밀번호가 올바르지 않아요.')
        elif new1 != new2:
            messages.error(request, '새 비밀번호가 서로 달라요.')
        elif user.check_password(new1):
            messages.error(request, '기존과 비밀번호가 같습니다.')
        else:
            try:
                validate_password(new1, user)   # Django 비번 정책 검증
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
            else:
                user.set_password(new1)
                user.save()
                update_session_auth_hash(request, user)   # 비번 바꿔도 로그인 유지
                messages.success(request, '비밀번호를 변경했어요.')
                return redirect('profile-edit')

    return render(request, 'accounts/password_change.html', {
        'active_tab': 'setting',
    })

@login_required
def budget_edit(request):
    """주간 예산 수정 (시간 단위 입력 → 분으로 저장)."""
    user = request.user

    if request.method == 'POST':
        hours = request.POST.get('weekly_budget_hours', '').strip()
        try:
            h = float(hours)
            if h <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '올바른 시간을 입력해주세요.')
        else:
            user.weekly_budget_min = round(h * 60)
            user.save(update_fields=['weekly_budget_min'])
            messages.success(request, '저장했어요.')
            return redirect('settings-page')

    # 현재 값을 시간으로 변환해서 폼에 표시
    current_hours = round(float(user.weekly_budget_min) / 60, 1)

    return render(request, 'accounts/budget_edit.html', {
        'active_tab': 'setting',
        'current_hours': current_hours,
    })

@login_required
def rate_edit(request):
    """활동별 환율 수정. 각 활동의 '1시간당 적립 분'을 입력받아 rate로 저장.
    검증: 0 < 분 < 60 (0분 초과 60분 미만)."""
    user = request.user
    activities = Activity.objects.filter(users=user)

    if request.method == 'POST':
        error = None
        updates = []   # (activity, new_rate) 임시 저장 후 일괄 반영

        for act in activities:
            raw = request.POST.get(f'activity_{act.id}', '').strip()
            try:
                minutes = int(raw)
            except (ValueError, TypeError):
                error = '숫자를 입력해주세요.'
                break

            # 0분 초과 60분 미만 검증
            if minutes <= 0 or minutes >= 60:
                error = '적립 시간은 0분 초과 60분 미만이어야 해요.'
                break

            new_rate = round(Decimal(minutes) / Decimal(60), 4)
            # 경계 방어 (0이나 1 나오지 않게)
            if new_rate <= Decimal('0'):
                new_rate = Decimal('0.0001')
            elif new_rate >= Decimal('1'):
                new_rate = Decimal('0.9999')
            updates.append((act, new_rate))

        if error:
            messages.error(request, error)
        else:
            for act, new_rate in updates:
                act.rate = new_rate
                act.save(update_fields=['rate'])
            messages.success(request, '저장했어요.')
            return redirect('settings-page')

    # 화면 표시용: 각 활동에 '분' 값 부착 (rate × 60)
    for act in activities:
        act.minutes = int(round(float(act.rate) * 60))

    return render(request, 'accounts/rate_edit.html', {
        'active_tab': 'setting',
        'activities': activities,
    })

@login_required
def unit_edit(request):
    """환산 단위 변경: converting_activity / conversion_base / conversion_unit."""
    user = request.user

    if request.method == 'POST':
        activity = request.POST.get('converting_activity', '').strip()
        base = request.POST.get('conversion_base', '').strip()
        unit = request.POST.get('conversion_unit', '').strip()

        try:
            units_per_hour = float(base)          # 입력: "1시간에 몇 개"
            if units_per_hour <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, '활동량은 0보다 큰 숫자여야 해요.')
        else:
            user.converting_activity = activity
            # 저장은 "1단위당 분" = 60 ÷ 시간당 개수
            user.conversion_base = round(Decimal('60') / Decimal(str(units_per_hour)), 2)
            user.conversion_unit = unit
            user.save(update_fields=['converting_activity', 'conversion_base', 'conversion_unit'])
            messages.success(request, '저장했어요.')
            return redirect('settings-page')

    base = float(user.conversion_base) if user.conversion_base else 0
    units_per_hour = round(60 / base, 2) if base > 0 else ''
    return render(request, 'accounts/unit_edit.html', {
        'active_tab': 'setting',
        'units_per_hour': units_per_hour,
    })
