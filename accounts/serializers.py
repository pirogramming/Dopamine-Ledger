from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from budget.models import Activity

User = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    """
    회원가입용 Serializer
    - 이메일, 닉네임, 비밀번호를 전달받아 새 유저를 생성합니다.
    """
    password = serializers.CharField(
        write_only=True,
        required=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('email', 'nickname', 'password')

    def validate_email(self, value):
        """
        이메일 중복 체크
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value

    def validate_nickname(self, value):
        """
        닉네임 중복 체크 (추가 권장)
        """
        if User.objects.filter(nickname=value).exists():
            raise serializers.ValidationError("이미 사용 중인 닉네임입니다.")
        return value

    def create(self, validated_data):
        """
        유저 생성 로직
        """
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            nickname=validated_data['nickname'],
            password=validated_data['password']
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    로그인용 Serializer
    - 이메일과 비밀번호를 받아 유저 인증을 진행합니다.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        # 1. 이메일 존재 여부 확인
        try: 
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "존재하지 않는 이메일 계정입니다."})

        # 2. 비밀번호 일치 여부 확인
        if not user.check_password(password):
            raise serializers.ValidationError({"password": "비밀번호가 올바르지 않습니다."})

        # 3. 계정 활성화 여부 확인
        if not user.is_active:
            raise serializers.ValidationError({"account": "비활성화된 계정입니다."})

        data['user'] = user
        return data


class UserResponseSerializer(serializers.ModelSerializer):
    """
    회원가입/로그인 성공 시 클라이언트에 응답해줄 기본 유저 정보 Serializer
    """
    class Meta:
        model = User
        fields = ('id', 'email', 'nickname', 'streak_days', 'credit_grade', 'weekly_budget_min')


class ActivityInputSerializer(serializers.Serializer):
    """
    개별 활동 단위 검증 (활동명과 분 모두 필수)
    """
    activity_type = serializers.CharField(max_length=30, required=True)
    minutes = serializers.IntegerField(min_value=1, max_value=59, required=True)

    def validate_minutes(self, value):
        # 0분 초과 60분 미만 (설정 화면과 동일 규칙)
        if value <= 0 or value >= 60:
            raise serializers.ValidationError('적립 시간은 0분 초과 60분 미만이어야 합니다.')
        return value


class OnboardingSerializer(serializers.ModelSerializer):
    activities = ActivityInputSerializer(many=True, write_only=True)

    class Meta:
        model = User
        fields = [
            'weekly_budget_min',
            'converting_activity',
            'conversion_base',
            'conversion_units_per_hour',
            'conversion_unit',
            'activities',
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        activities_data = validated_data.pop('activities', [])

        instance = super().update(instance, validated_data)

        if activities_data:
            Activity.objects.filter(users=instance).delete()

            activities_to_create = []
            for item in activities_data:
                act_type = item['activity_type'].strip()
                minutes = item['minutes']

                # validate_minutes(0<분<60)가 이미 보장하므로 분기 불필요
                calculated_rate = round(Decimal(minutes) / Decimal(60), 4)

                activities_to_create.append(
                    Activity(
                        users=instance,
                        activity_type=act_type,
                        rate=calculated_rate
                    )
                )

            Activity.objects.bulk_create(activities_to_create)

        return instance