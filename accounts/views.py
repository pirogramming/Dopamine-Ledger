from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token

from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserResponseSerializer
)

from django.shortcuts import render

# Create your views here.
class SignupView(APIView):
    """
    회원가입 API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # 회원가입 성공 시 인증 토큰 자동 생성
            token, _ = Token.objects.get_or_create(user=user)

            response_data = {
                "message": "회원가입이 완료되었습니다.",
                "token": token.key,
                "user": UserResponseSerializer(user).data
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        # 유효성 검사 실패 시
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    로그인 API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            token, _ = Token.objects.get_or_create(user=user)

            response_data = {
                "message": "로그인에 성공하였습니다.",
                "token": token.key,
                "user": UserResponseSerializer(user).data
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # 로그인 실패 시
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)