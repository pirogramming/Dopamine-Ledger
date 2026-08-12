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
CARD_HEIGHT = 1704

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
    """분을 'X시간 Y분' 문자열로. weekly_report.html의 formatHoursMins와 동일 로직."""
    total_mins = int(total_mins or 0)
    hrs = total_mins // 60
    mins = total_mins % 60
    if hrs > 0:
        return f"{hrs}시간 {mins}분"
    return f"{mins}분"


def _draw_metric_column(draw, cx, cy_label, label, value, value_color,
                        font_label, font_value):
    """3분할 지표 한 칸(라벨 + 값)을 중앙정렬로 그림."""
    draw.text((cx, cy_label), label,
              fill=COLOR_GRAY_SUB, font=font_label, anchor="mm")
    draw.text((cx, cy_label + 70), value,
              fill=value_color, font=font_value, anchor="mm")


def generate_weekly_share_card(
    nickname: str,
    this_spend_min: int,
    this_earn_min: int,
    spend_diff_min: int,
    week_label: str,
    alt_text: str = "",
) -> bytes:
    """
    주간 결산을 카드 이미지(PNG 바이트)로 반환한다.

    인자:
        nickname       : 사용자 닉네임
        this_spend_min : 이번 주 지출(숏폼) 분
        this_earn_min  : 이번 주 수입(활동) 분
        spend_diff_min : 전주 대비 지출 차이(분). 음수면 줄었음.
        week_label     : '2026년 08월 10일 ~ 08월 16일' 같은 주차 라벨
        alt_text       : 대체재 환산 문구 (예: '책 0.8권'). 비어있으면 렌더 안 함.

    리턴: PNG 바이트 (view에서 HttpResponse로 감싸서 반환)
    """
    # --- 1) 캔버스 ---
    img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # --- 2) 폰트 로드 ---
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 56)     # "이번 주 결산"
    font_week = ImageFont.truetype(FONT_REGULAR_PATH, 30)   # 주차 라벨
    font_hero_label = ImageFont.truetype(FONT_REGULAR_PATH, 34)  # "이번 주 절약 시간"
    font_hero_value = ImageFont.truetype(FONT_BOLD_PATH, 110)    # 큰 숫자
    font_alt = ImageFont.truetype(FONT_REGULAR_PATH, 34)    # 대체재 환산
    font_metric_label = ImageFont.truetype(FONT_REGULAR_PATH, 28)  # 3분할 라벨
    font_metric_value = ImageFont.truetype(FONT_BOLD_PATH, 40)     # 3분할 값
    font_footer_sub = ImageFont.truetype(FONT_REGULAR_PATH, 26)
    font_footer_brand = ImageFont.truetype(FONT_BOLD_PATH, 30)

    center_x = CARD_WIDTH / 2

    # --- 3) 상단: 타이틀 + 주차 ---
    draw.text((center_x, 110), "이번 주 결산",
              fill=COLOR_BLACK, font=font_title, anchor="mm")
    draw.text((center_x, 175), week_label,
              fill=COLOR_GRAY_SUB, font=font_week, anchor="mm")

    # --- 4) 흰 카드 박스 (summary-card 톤) ---
    card_x1, card_y1 = 60, 260
    card_x2, card_y2 = CARD_WIDTH - 60, CARD_HEIGHT - 220
    draw.rounded_rectangle(
        [(card_x1, card_y1), (card_x2, card_y2)],
        radius=32,
        fill=COLOR_CARD,
        outline=COLOR_GRAY_LINE,
        width=2,
    )

    # --- 5) 카드 내부: 절약 시간 크게 (수입 시간을 절약분으로 강조) ---
    draw.text((center_x, card_y1 + 110), "이번 주 벌어들인 시간",
              fill=COLOR_GRAY_SUB, font=font_hero_label, anchor="mm")

    hero_value = _format_hours_mins(this_earn_min)
    draw.text((center_x, card_y1 + 240), hero_value,
              fill=COLOR_ORANGE, font=font_hero_value, anchor="mm")

    # 대체재 환산 (2줄: '= 책 0.8권' + '숏폼에 쓴 만큼의 시간')
    # alt_text는 view에서 { "converted": "책 0.8권", "context": "숏폼에 쓴 만큼의 시간" } 형태로 넘김
    # 문자열이 넘어오면 옛날 방식(한 줄)도 지원 — 안전장치
    if alt_text:
        if isinstance(alt_text, dict):
            converted = alt_text.get("converted", "")
            context_line = alt_text.get("context", "")
            if converted:
                draw.text((center_x, card_y1 + 340), f"= {converted}",
                          fill=COLOR_ORANGE, font=font_alt, anchor="mm")
            if context_line:
                draw.text((center_x, card_y1 + 395), context_line,
                          fill=COLOR_GRAY_SUB, font=font_alt, anchor="mm")
        else:
            # 문자열이 그대로 들어오면 한 줄로 (하위 호환)
            draw.text((center_x, card_y1 + 340), f"= {alt_text}",
                      fill=COLOR_BLACK, font=font_alt, anchor="mm")

    # --- 6) 카드 하단부: 3분할 지표 (metrics-container 톤) ---
    metrics_label_y = card_y2 - 260
    col_w = (card_x2 - card_x1) / 3

    # 사용 시간
    _draw_metric_column(
        draw, card_x1 + col_w * 0.5, metrics_label_y,
        "사용 시간", _format_hours_mins(this_spend_min),
        COLOR_BLACK, font_metric_label, font_metric_value,
    )
    # 수입 시간
    _draw_metric_column(
        draw, card_x1 + col_w * 1.5, metrics_label_y,
        "수입 시간", _format_hours_mins(this_earn_min),
        COLOR_BLACK, font_metric_label, font_metric_value,
    )
    # 전주 대비 (음수=줄었음=초록, 양수=늘었음=주황)
    diff_val = int(spend_diff_min or 0)
    if diff_val <= 0:
        diff_str = f"-{_format_hours_mins(abs(diff_val))}"
        diff_color = COLOR_GREEN
    else:
        diff_str = f"+{_format_hours_mins(diff_val)}"
        diff_color = COLOR_ORANGE
    _draw_metric_column(
        draw, card_x1 + col_w * 2.5, metrics_label_y,
        "전주 대비", diff_str, diff_color,
        font_metric_label, font_metric_value,
    )

    # --- 7) 하단: 닉네임 + 서비스명 ---
    draw.text((center_x, CARD_HEIGHT - 130),
              f"@{nickname}", fill=COLOR_GRAY_SUB,
              font=font_footer_sub, anchor="mm")
    draw.text((center_x, CARD_HEIGHT - 80),
              "도파민 가계부", fill=COLOR_ORANGE,
              font=font_footer_brand, anchor="mm")

    # --- 8) PNG 바이트로 반환 ---
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()