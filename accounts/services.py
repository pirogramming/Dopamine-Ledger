from decimal import Decimal

GRADE_CONFIG = {
    'LEVEL_0': {
        'name': '도파민 노예',
        'min_days': 0,
        'bonus_rate': 0.00,
        'dialogue_before': '숏폼의 굴레에서 벗어날 준비가 되셨나요?',
        'dialogue_after': '첫 걸음을 내디뎠어요! 다음 레벨을 향해 달려보아요.',
    },
    'LEVEL_1': {
        'name': '도파민 디톡서',
        'min_days': 3,
        'bonus_rate': 0.00,
        'dialogue_before': '뇌가 휴식하고 있어요. 오늘도 뇌를 쉬게 해볼까요?',
        'dialogue_after': '디톡스 완료! 7일 달성 시 우대 혜택이 열려요!',
    },
    'LEVEL_2': {
        'name': '시간 연금술사',
        'min_days': 7,
        'bonus_rate': 0.03,
        'dialogue_before': '시간을 자산으로 바꾸는 연금술사님, 마감해볼까요?',
        'dialogue_after': '연금술 성공! +3% 환율 우대가 적용되었어요.',
    },
    'LEVEL_3': {
        'name': '도파민 정복자',
        'min_days': 14,
        'bonus_rate': 0.05,
        'dialogue_before': '유혹을 완벽히 제어 중이시군요! 오늘 마감도 고고!',
        'dialogue_after': '정복 완료! +5% 환율 우대 혜택을 챙겨드려요.',
    },
    'LEVEL_4': {
        'name': '절제의 신',
        'min_days': 21,
        'bonus_rate': 0.10,
        'dialogue_before': '신성한 절제의 경지! 오늘의 마감을 기록하세요.',
        'dialogue_after': '절제의 신 강림! 최고 우대 혜택 +10% 적용 완료!',
    },
}

GRADE_ORDER = ['LEVEL_0', 'LEVEL_1', 'LEVEL_2', 'LEVEL_3', 'LEVEL_4']


def calculate_grade_by_streak(streak_days: int) -> str:
    """연속 일수에 따른 리그 등급키 반환"""
    if streak_days >= 21:
        return 'LEVEL_4'
    elif streak_days >= 14:
        return 'LEVEL_3'
    elif streak_days >= 7:
        return 'LEVEL_2'
    elif streak_days >= 3:
        return 'LEVEL_1'
    return 'LEVEL_0'

def get_exchange_bonus_rate(grade_key: str) -> float:
    """리그 등급키 기반 보너스 우대율(0.00 ~ 0.10) 반환"""
    return GRADE_CONFIG.get(grade_key, {}).get('bonus_rate', 0.00)

def demote_grade_one_step(current_grade_key: str) -> str:
    """마감 놓침/실패 시 1단계만 하락한 등급키 반환"""
    try:
        idx = GRADE_ORDER.index(current_grade_key)
        return GRADE_ORDER[max(0, idx - 1)]
    except ValueError:
        return 'LEVEL_0'


def calculate_reward_minutes(
    duration_min: int,
    base_rate: Decimal | float,
    bonus_rate: Decimal | float,
) -> int:
    """
    활동 시간(duration_min)에 (활동 환산율 rate + 리그 우대율 bonus_rate)을 더해 최종 적립 분을 계산.
    최종 적립 시간은 최대 59분으로 제한.
    """
    # Decimal로 안전하게 합산 (0.5000 + 0.03 = 0.5300)
    total_rate = Decimal(str(base_rate)) + Decimal(str(bonus_rate))

    # 활동 분 * 최종 환산율 (버림 처리 후 int 변환)
    earned = int(Decimal(duration_min) * total_rate)

    # 1회 최대 59분 상한선 적용
    return min(earned, 59)


def get_league_dialogue(grade_key: str, is_closed: bool) -> str:
    """마감 전/후 상태에 따른 캐릭터 말풍선 멘트 반환"""
    config = GRADE_CONFIG.get(grade_key, GRADE_CONFIG['LEVEL_0'])
    return config['dialogue_after'] if is_closed else config['dialogue_before']