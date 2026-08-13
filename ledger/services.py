from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DailyClose, EarnRecord, SpendRecord


# ============================================================
# 주간 결산 공유 카드 (Pillow)
# - 매 요청마다 새로 그림, 저장하지 않음
# - 규격/색/폰트: common.css & weekly_report.css 값 그대로
# ============================================================
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

#==========
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from PIL import Image, ImageDraw, ImageFont

from .models import DailyClose, EarnRecord, SpendRecord


def get_today_record_summary(user):
    """
    사용자의 오늘 수입/지출 정보와 마감 여부를 조회한다.
    """
    today = timezone.localdate()

    earn_records = EarnRecord.objects.filter(
        users=user,
        earn_date=today,
    )
    spend_records = SpendRecord.objects.filter(
        users=user,
        spend_date=today,
    )

    today_earn = (
        earn_records.aggregate(total=Sum("earn_min"))["total"]
        or 0
    )
    today_spend = (
        spend_records.aggregate(total=Sum("duration_min"))["total"]
        or 0
    )

    is_closed = DailyClose.objects.filter(
        users=user,
        close_date=today,
    ).exists()

    return {
        "today": today,
        "today_earn": today_earn,
        "today_spend": today_spend,
        "has_earn_record": earn_records.exists(),
        "has_spend_record": spend_records.exists(),
        "is_closed": is_closed,
        "earn_activity": (
            earn_records.first().activity.activity_type
            if earn_records.exists()
            else None
        ),
    }


def close_today(user):
    """
    하루 마감을 처리하고 연속 마감일을 갱신한다.
    """

    today = timezone.localdate()

    # 이미 마감했는지 확인
    if DailyClose.objects.filter(
        users=user,
        close_date=today,
    ).exists():
        raise ValueError("오늘은 이미 마감했습니다.")

    summary = get_today_record_summary(user)

    # 오늘 기록이 하나도 없는 경우
    has_any_record = (
        summary["has_earn_record"]
        or summary["has_spend_record"]
    )

    if not has_any_record:
        raise ValueError(
            "오늘 기록이 없습니다."
        )

    yesterday = today - timedelta(days=1)

    previous_close = (
        DailyClose.objects.filter(
            users=user,
            close_date__lt=today,
        )
        .order_by("-close_date")
        .first()
    )

    with transaction.atomic():
        daily_close = DailyClose.objects.create(
            users=user,
            close_date=today,
            closed_at=timezone.now(),
        )

        if (
            previous_close
            and previous_close.close_date == yesterday
        ):
            user.streak_days += 1
        else:
            user.streak_days = 1

        user.save(update_fields=["streak_days"])

    return daily_close




# 카드 규격 (폰 프레임 393×852의 2배 해상도)
CARD_WIDTH = 786
CARD_HEIGHT = 1200

# 색 (common.css / weekly_report.css 값 그대로)
COLOR_BG = "#fdfcf9"          # phone-frame 배경
COLOR_CARD = "#ffffff"         # summary-card 흰 카드
COLOR_BLACK = "#000000"
COLOR_ORANGE = "#ff7a00"       # 강조(지출/증가)
COLOR_GREEN = "#4dad44"        # 절감(감소)
COLOR_GRAY_SUB = "#70737c"     # 라벨/보조 텍스트
COLOR_GRAY_LINE = "#c7c7c7"    # 카드 테두리/구분선

# 폰트 경로 (1단계에서 넣은 파일)
_FONT_DIR = Path(settings.BASE_DIR) / "ledger" / "static" / "ledger" / "fonts"
FONT_REGULAR_PATH = str(_FONT_DIR / "Pretendard-Regular.otf")
FONT_BOLD_PATH = str(_FONT_DIR / "Pretendard-Bold.otf")


def _format_hours_mins(total_mins) -> str:
    total_mins = int(total_mins or 0)
    hrs = total_mins // 60
    mins = total_mins % 60
    if hrs > 0:
        return f"{hrs}시간 {mins}분"
    return f"{mins}분"


def _earn_diff_message(diff_min: int) -> str:
    """수입 차이 → 자연어 문구."""
    if diff_min > 0:
        return f"벌어들인 시간이 저번 주 대비 {_format_hours_mins(diff_min)}이 늘었어요!"
    if diff_min < 0:
        return f"벌어들인 시간이 저번 주 대비 {_format_hours_mins(abs(diff_min))} 줄었어요."
    return "벌어들인 시간이 저번 주와 같아요."


def _spend_diff_message(diff_min: int) -> str:
    """지출 차이 → 자연어 문구."""
    if diff_min < 0:
        return f"숏폼을 전 주 대비 {_format_hours_mins(abs(diff_min))} 덜 사용하셨어요!"
    if diff_min > 0:
        return f"숏폼을 전 주 대비 {_format_hours_mins(diff_min)} 더 사용하셨어요."
    return "숏폼 사용 시간이 저번 주와 같아요."


def _draw_block(draw, cx, y_top, label_text, value_text, value_color,
                alt_text, alt_color, diff_message,
                font_label, font_value, font_alt, font_diff) -> int:
    """
    수입/지출 블록 하나를 그린다. 시작 y좌표를 받아 마지막 y좌표를 반환.
    구조 (위→아래):
        [라벨]              — 회색
        [큰 값]             — value_color (초록/주황)
        [= 환산문구]         — alt_color (초록/주황)
        [차이 문구]         — 검정
    """
    # 라벨 (좌측정렬 느낌으로 중앙에서 살짝 왼쪽 배치는 생략하고 중앙정렬 통일)
    draw.text((cx, y_top), label_text,
              fill=COLOR_GRAY_SUB, font=font_label, anchor="mm")

    # 큰 값
    y_value = y_top + 90
    draw.text((cx, y_value), value_text,
              fill=value_color, font=font_value, anchor="mm")

    # 대체재 환산 (환산 활동 미설정 시 스킵)
    y_alt = y_value + 85
    if alt_text:
        draw.text((cx, y_alt), f"= {alt_text}",
                  fill=alt_color, font=font_alt, anchor="mm")
        y_diff = y_alt + 70
    else:
        y_diff = y_alt

    # 차이 문구 (검정)
    draw.text((cx, y_diff), diff_message,
              fill=COLOR_BLACK, font=font_diff, anchor="mm")

    return y_diff  # 이 블록의 마지막 y


def generate_weekly_share_card(
    nickname: str,
    week_label: str,
    this_earn_min: int,
    this_spend_min: int,
    earn_diff_min: int,
    spend_diff_min: int,
    earn_alt: str = "",
    spend_alt: str = "",
) -> bytes:
    """
    주간 결산을 카드 이미지(PNG 바이트)로 반환한다.

    새 구조:
        상단 타이틀·주차
        [흰 카드]
            [수입 블록 - 초록]
                이번주 벌어들인 시간:
                    2시간 0분 (초록, 큰)
                = 코딩공부 6.0페이지 (초록)
                벌어들인 시간이 저번 주 대비 30분이 늘었어요! (검정)
            [지출 블록 - 주황]
                이번주 숏폼에 사용한 시간:
                    2시간 0분 (주황, 큰)
                = 코딩공부 6.0페이지 (주황)
                숏폼을 전 주 대비 30분 덜 사용하셨어요! (검정)
        하단: 닉네임 + 서비스명
    """
    img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # --- 폰트 (기존 크기 유지) ---
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 56)       # "이번 주 결산"
    font_week = ImageFont.truetype(FONT_REGULAR_PATH, 30)     # 주차 라벨
    font_block_label = ImageFont.truetype(FONT_REGULAR_PATH, 32)  # "이번주 벌어들인 시간:"
    font_block_value = ImageFont.truetype(FONT_BOLD_PATH, 70)     # 큰 숫자
    font_block_alt = ImageFont.truetype(FONT_REGULAR_PATH, 32)    # 대체재 환산
    font_block_diff = ImageFont.truetype(FONT_REGULAR_PATH, 28)   # 차이 문구
    font_footer_sub = ImageFont.truetype(FONT_REGULAR_PATH, 26)
    font_footer_brand = ImageFont.truetype(FONT_BOLD_PATH, 30)

    center_x = CARD_WIDTH / 2

    # --- 상단: 타이틀 + 주차 ---
    draw.text((center_x, 110), "이번 주 결산",
              fill=COLOR_BLACK, font=font_title, anchor="mm")
    draw.text((center_x, 175), week_label,
              fill=COLOR_GRAY_SUB, font=font_week, anchor="mm")

    # --- 흰 카드 박스 ---
    card_x1, card_y1 = 60, 240
    card_x2, card_y2 = CARD_WIDTH - 60, CARD_HEIGHT - 180
    draw.rounded_rectangle(
        [(card_x1, card_y1), (card_x2, card_y2)],
        radius=32,
        fill=COLOR_CARD,
        outline=COLOR_GRAY_LINE,
        width=2,
    )

    # --- 수입 블록 (초록) ---
    earn_block_top = card_y1 + 80
    earn_block_bottom = _draw_block(
        draw, center_x, earn_block_top,
        label_text="이번주 벌어들인 시간",
        value_text=_format_hours_mins(this_earn_min),
        value_color=COLOR_GREEN,
        alt_text=earn_alt,
        alt_color=COLOR_GREEN,
        diff_message=_earn_diff_message(earn_diff_min),
        font_label=font_block_label,
        font_value=font_block_value,
        font_alt=font_block_alt,
        font_diff=font_block_diff,
    )

    # --- 블록 사이 구분선 (얇은 회색 선) ---
    divider_y = earn_block_bottom + 60
    draw.line(
        [(card_x1 + 60, divider_y), (card_x2 - 60, divider_y)],
        fill=COLOR_GRAY_LINE, width=1,
    )

    # --- 지출 블록 (주황) ---
    spend_block_top = divider_y + 60
    _draw_block(
        draw, center_x, spend_block_top,
        label_text="이번주 숏폼에 사용한 시간",
        value_text=_format_hours_mins(this_spend_min),
        value_color=COLOR_ORANGE,
        alt_text=spend_alt,
        alt_color=COLOR_ORANGE,
        diff_message=_spend_diff_message(spend_diff_min),
        font_label=font_block_label,
        font_value=font_block_value,
        font_alt=font_block_alt,
        font_diff=font_block_diff,
    )

    # --- 하단: 닉네임 + 서비스명 ---
    draw.text((center_x, CARD_HEIGHT - 110),
              f"@{nickname}", fill=COLOR_GRAY_SUB,
              font=font_footer_sub, anchor="mm")
    draw.text((center_x, CARD_HEIGHT - 60),
              "도파민 가계부", fill=COLOR_ORANGE,
              font=font_footer_brand, anchor="mm")

    # --- PNG 반환 ---
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()