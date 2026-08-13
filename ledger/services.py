from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from PIL import Image, ImageDraw, ImageFont

from .models import DailyClose, EarnRecord, SpendRecord


# ============================================================
# 오늘 요약 & 하루 마감
# ============================================================

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


# ============================================================
# 주간 결산 공유 카드 (Pillow)
# - 매 요청마다 새로 그림, 저장하지 않음
# - 규격/색/폰트: common.css & weekly_report.css 값 그대로
# ============================================================

# 카드 규격 (폰 프레임 393×852의 2배 해상도)
CARD_WIDTH = 786
CARD_HEIGHT = 1200

# 색 (common.css / weekly_report.css 값 그대로)
COLOR_BG = "#fdfcf9"          # phone-frame 배경
COLOR_CARD = "#ffffff"         # summary-card 흰 카드
COLOR_BLACK = "#000000"
COLOR_ORANGE = "#ff7a00"       # 강조(지출 테마)
COLOR_GREEN = "#4dad44"        # 강조(수입 테마)
COLOR_GRAY_SUB = "#70737c"     # 라벨/보조 텍스트
COLOR_GRAY_LINE = "#c7c7c7"    # 카드 테두리/구분선
COLOR_GREEN_BG = "#eaf7ea"     # 좋은 방향 배지 연한 배경 (초록)
COLOR_ORANGE_BG = "#fff1e6"    # 나쁜 방향 배지 연한 배경 (주황)
COLOR_GRAY_BG = "#f0f0f0"      # 변화 없음 배지 연한 배경 (회색)

# 폰트 경로
_FONT_DIR = Path(settings.BASE_DIR) / "ledger" / "static" / "ledger" / "fonts"
FONT_REGULAR_PATH = str(_FONT_DIR / "Pretendard-Regular.otf")
FONT_BOLD_PATH = str(_FONT_DIR / "Pretendard-Bold.otf")


def _format_hours_mins(total_mins) -> str:
    """분을 'X시간 Y분' 문자열로."""
    total_mins = int(total_mins or 0)
    hrs = total_mins // 60
    mins = total_mins % 60
    if hrs > 0:
        return f"{hrs}시간 {mins}분"
    return f"{mins}분"


def _earn_diff_style(diff_min: int):
    """
    수입 차이 → (배지 텍스트, 텍스트 색, 배경 색) 튜플.
    수입은 늘면 좋음(초록), 줄면 나쁨(주황), 같으면 중립(회색).
    """
    diff_min = int(diff_min or 0)
    if diff_min > 0:
        text = f"↑ 저번 주보다 {_format_hours_mins(diff_min)} 늘었어요"
        return text, COLOR_GREEN, COLOR_GREEN_BG
    if diff_min < 0:
        text = f"↓ 저번 주보다 {_format_hours_mins(abs(diff_min))} 줄었어요"
        return text, COLOR_ORANGE, COLOR_ORANGE_BG
    text = "— 저번 주와 같아요"
    return text, COLOR_GRAY_SUB, COLOR_GRAY_BG


def _spend_diff_style(diff_min: int):
    """
    지출 차이 → (배지 텍스트, 텍스트 색, 배경 색) 튜플.
    지출은 줄면 좋음(초록), 늘면 나쁨(주황), 같으면 중립(회색).
    """
    diff_min = int(diff_min or 0)
    if diff_min > 0:
        text = f"↑ 저번 주보다 {_format_hours_mins(diff_min)} 늘었어요"
        return text, COLOR_ORANGE, COLOR_ORANGE_BG
    if diff_min < 0:
        text = f"↓ 저번 주보다 {_format_hours_mins(abs(diff_min))} 줄었어요"
        return text, COLOR_GREEN, COLOR_GREEN_BG
    text = "— 저번 주와 같아요"
    return text, COLOR_GRAY_SUB, COLOR_GRAY_BG


def _draw_pill(draw, cx, cy, text, text_color, bg_color, font,
               padding_x=26, padding_y=14):
    """
    둥근 알약 모양 배지를 (cx, cy) 중심에 그린다.
    텍스트 크기를 먼저 재서 배지 크기를 텍스트에 맞춰 자동 조정.
    반환값: 배지 하단 y좌표 (다음 요소 배치용)
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pill_w = text_w + padding_x * 2
    pill_h = text_h + padding_y * 2

    x1 = cx - pill_w / 2
    y1 = cy - pill_h / 2
    x2 = cx + pill_w / 2
    y2 = cy + pill_h / 2

    draw.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=pill_h / 2,   # 반원형 캡슐 모양
        fill=bg_color,
    )
    draw.text((cx, cy), text, fill=text_color, font=font, anchor="mm")

    return y2


def _draw_block(draw, cx, y_top, label_text, value_text, value_color,
                alt_text, alt_color, diff_text, diff_text_color, diff_bg_color,
                font_label, font_value, font_alt, font_diff) -> int:
    """
    수입/지출 블록 하나를 그린다. 시작 y좌표를 받아 마지막 y좌표를 반환.
    구조 (위→아래):
        [라벨]              — 회색
        [큰 값]             — value_color (초록/주황, 블록 테마 색)
        [= 환산문구]         — alt_color (초록/주황, 블록 테마 색)
        [증감 배지]          — 아이콘+문구, 방향 기반 색 (초록/주황/회색)
    """
    draw.text((cx, y_top), label_text,
              fill=COLOR_GRAY_SUB, font=font_label, anchor="mm")

    y_value = y_top + 70
    draw.text((cx, y_value), value_text,
              fill=value_color, font=font_value, anchor="mm")

    y_alt = y_value + 65
    if alt_text:
        draw.text((cx, y_alt), f"= {alt_text}",
                  fill=alt_color, font=font_alt, anchor="mm")
        y_pill_center = y_alt + 90
    else:
        y_pill_center = y_alt + 25

    y_bottom = _draw_pill(
        draw, cx, y_pill_center, diff_text,
        text_color=diff_text_color,
        bg_color=diff_bg_color,
        font=font_diff,
    )

    return y_bottom


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

    구조:
        상단 타이틀·주차
        [흰 카드]
            [수입 블록 - 큰 값은 초록 테마]
                이번주 벌어들인 시간
                    2시간 0분 (초록, 큰)
                = 코딩공부 6.0페이지 (초록)
                [증감 배지: 방향 기반 색]
            [지출 블록 - 큰 값은 주황 테마]
                이번주 숏폼에 사용한 시간
                    2시간 30분 (주황, 큰)
                = 코딩공부 7.5페이지 (주황)
                [증감 배지: 방향 기반 색]
        하단: 닉네임 + 서비스명
    """
    img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # --- 폰트 ---
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 56)       # "이번 주 결산"
    font_week = ImageFont.truetype(FONT_REGULAR_PATH, 30)     # 주차 라벨
    font_block_label = ImageFont.truetype(FONT_REGULAR_PATH, 32)  # "이번주 벌어들인 시간"
    font_block_value = ImageFont.truetype(FONT_BOLD_PATH, 50)     # 큰 숫자
    font_block_alt = ImageFont.truetype(FONT_REGULAR_PATH, 32)    # 대체재 환산
    font_block_diff = ImageFont.truetype(FONT_REGULAR_PATH, 28)   # 증감 배지
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

    # --- 수입 블록 ---
    earn_diff_text, earn_diff_color, earn_diff_bg = _earn_diff_style(earn_diff_min)

    earn_block_top = card_y1 + 80
    earn_block_bottom = _draw_block(
        draw, center_x, earn_block_top,
        label_text="이번주 벌어들인 시간",
        value_text=_format_hours_mins(this_earn_min),
        value_color=COLOR_GREEN,           # 큰 값은 항상 초록 (수입 = 초록 테마)
        alt_text=earn_alt,
        alt_color=COLOR_GREEN,
        diff_text=earn_diff_text,
        diff_text_color=earn_diff_color,   # 배지 텍스트 색: 방향 기반
        diff_bg_color=earn_diff_bg,        # 배지 배경 색: 방향 기반
        font_label=font_block_label,
        font_value=font_block_value,
        font_alt=font_block_alt,
        font_diff=font_block_diff,
    )

    # --- 블록 사이 구분선 ---
    divider_y = earn_block_bottom + 50
    draw.line(
        [(card_x1 + 60, divider_y), (card_x2 - 60, divider_y)],
        fill=COLOR_GRAY_LINE, width=1,
    )

    # --- 지출 블록 ---
    spend_diff_text, spend_diff_color, spend_diff_bg = _spend_diff_style(spend_diff_min)

    spend_block_top = divider_y + 80
    _draw_block(
        draw, center_x, spend_block_top,
        label_text="이번주 숏폼에 사용한 시간",
        value_text=_format_hours_mins(this_spend_min),
        value_color=COLOR_ORANGE,          # 큰 값은 항상 주황 (지출 = 주황 테마)
        alt_text=spend_alt,
        alt_color=COLOR_ORANGE,
        diff_text=spend_diff_text,
        diff_text_color=spend_diff_color,  # 배지 텍스트 색: 방향 기반
        diff_bg_color=spend_diff_bg,       # 배지 배경 색: 방향 기반
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