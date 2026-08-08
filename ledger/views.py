from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SpendRecordForm, EarnRecordForm
from .models import SpendRecord, EarnRecord

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.http import JsonResponse

@login_required
def spend_record_create(request):
    """
    지출 기록 생성 뷰.
    - GET: 빈 폼을 보여줌
    - POST: 검증 후 저장. user는 폼 필드로 노출하지 않고 request.user로 직접 채움(다른 사람 이름으로 기록 남기는 것 방지)
    """
    if request.method == 'POST':
        form = SpendRecordForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.users = request.user  # 모델 필드명이 user -> users로 바뀐 것 반영
            instance.save()
            # Post-Redirect-Get: 새로고침 시 중복 저장 방지
            return redirect('ledger:record_choice')
        # form.is_valid()가 False면 여기서 form을 새로 안 만들고
        # 에러가 담긴 form 그대로 아래 render로 넘어감 (에러 메시지 보존)
    else:
        # GET 요청 분기가 없어서 아무것도 반환 안 하던 버그 수정
        form = SpendRecordForm()

    return render(request, 'ledger/spend_record_form.html', {'form': form})


@login_required
def spend_record_list(request):
    """
    지출 기록 목록 조회 뷰.
    - 본인 기록만 조회(다른 유저 기록 노출 금지)
    - 최신순 정렬
    * 이 쿼리셋은 나중에 홈 화면에서도 최근 지출 미리보기 용도로 재사용될 수 있음 - 2주차 담당자한테 공유 예정
    """
    # 필드명이 users라서 필터 키워드도 맞춰줘야 함 (안 그러면 FieldError)
    records = SpendRecord.objects.filter(users=request.user).order_by('-spend_start')
    return render(request, 'ledger/spend_record_list.html', {'records': records})


@login_required
def earn_record_create(request):
    """
    수입 기록 생성 뷰
    - GET: entry_mode(타이머/수동입력)로 어떤 화면을 보여줄지 결정
    - POST: entry_mode에 따라 폼이 다르게 검증/계산됨
    """
    if request.method == 'POST':
        form = EarnRecordForm(request.POST, user=request.user)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.users = request.user  # user -> users
            instance.save()
            return redirect('ledger:record_choice')
        # 검증 실패 시 새 폼으로 덮어쓰지 않고 에러 담긴 form 그대로 유지
    else:
        entry_mode = request.GET.get('mode', 'manual')
        form = EarnRecordForm(initial={'entry_mode': entry_mode}, user=request.user)

    return render(request, 'ledger/earn_record_form.html', {'form': form})


@login_required
def earn_record_list(request):
    """수입 기록 목록 조회 뷰, 본인 기록만 최신순으로"""
    records = EarnRecord.objects.filter(users=request.user).order_by('-earn_start')
    return render(request, 'ledger/earn_record_list.html', {'records': records})

@login_required
def record_choice(request):
    """기록하기 진입 화면 - 지출/수입 선택만 보여주는 단순 뷰"""
    return render(request, 'ledger/record_choice.html')


@login_required
def weekly_report(request):
    user = request.user
    today = timezone.now().date()

    # 1. 날짜 범위 산출
    this_start = today - timedelta(days=today.weekday())
    this_end = this_start + timedelta(days=6)

    last_start = this_start - timedelta(days=7)
    last_end = this_start - timedelta(days=1)

    # 2. 숏폼 지출 집계
    this_spend_int = SpendRecord.objects.filter(
        users=user, spend_date__range=[this_start, this_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    last_spend = SpendRecord.objects.filter(
        users=user, spend_date__range=[last_start, last_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    # 3. 활동 적립 집계
    this_earn_qs = EarnRecord.objects.filter(
        users=user, earn_date__range=[this_start, this_end]
    )
    last_earn_qs = EarnRecord.objects.filter(
        users=user, earn_date__range=[last_start, last_end]
    )

    this_earn_total = this_earn_qs.aggregate(total=Sum('earn_min'))['total'] or 0
    last_earn_total = last_earn_qs.aggregate(total=Sum('earn_min'))['total'] or 0

    # 4. 차이 수치 계산
    spend_diff = this_spend_int - last_spend
    earn_diff = this_earn_total - last_earn_total

    # 5. 수치 반올림 처리
    this_spend_int_int = int(round(this_spend_int))
    spend_diff_int = int(round(spend_diff))
    this_earn_total_int = int(round(this_earn_total))
    earn_diff_int = int(round(earn_diff))

    # 5. 활동별 집계
    this_activity_map = {
        item['activity__activity_type']: int(round(item['total'] or 0))
        for item in this_earn_qs.values('activity__activity_type').annotate(total=Sum('earn_min'))
    }
    last_activity_map = {
        item['activity__activity_type']: int(round(item['total'] or 0))
        for item in last_earn_qs.values('activity__activity_type').annotate(total=Sum('earn_min'))
    }

    best_activity = None
    max_increase = 0

    for act_name, this_min in this_activity_map.items():
        last_min = last_activity_map.get(act_name, 0)
        increase = this_min - last_min
        if increase > max_increase:
            max_increase = increase
            best_activity = act_name

    # --------------------------------------------------
    # 6. 칭찬 문구 조건 분기 (지난주 데이터 부재 시 예외 처리 최우선)
    # --------------------------------------------------
    is_no_last_data = (last_spend == 0) and (last_earn_total == 0)

    if is_no_last_data:
        if this_earn_total > 0:
            total_hrs = int(this_earn_total // 60)
            total_mins = int(this_earn_total % 60)
            earn_str = f"{total_hrs}시간 {total_mins}분" if total_hrs > 0 else f"{total_mins}분"
            praise_message = f"이번 주 총 {earn_str} 동안 멋지게 활동하며 시간을 벌었어요!"
        else:
            praise_message = "꾸준히 기록하며 도파민을 관리해 보아요!"

    elif best_activity and max_increase > 0:
        this_hrs = int(this_activity_map[best_activity] // 60)
        this_mins = int(this_activity_map[best_activity] % 60)
        inc_hrs = int(max_increase // 60)
        inc_mins = int(max_increase % 60)
        
        this_str = f"{this_hrs}시간 {this_mins}분" if this_hrs > 0 else f"{this_mins}분"
        inc_str = f"{inc_hrs}시간 {inc_mins}분" if inc_hrs > 0 else f"{inc_mins}분"
        
        praise_message = f"이번 주 {best_activity} {this_str}, 지난주보다 {inc_str} 늘었어요!"

    elif spend_diff < 0:
        praise_message = f"이번 주는 지난주보다 숏폼을 {abs(spend_diff)}분 줄였어요!"

    else:
        praise_message = "꾸준히 기록하며 도파민을 관리해 보아요!"


    return JsonResponse(
        {
            "praise_message": praise_message,
            "this_spend_int_min": this_spend_int,
            "spend_diff_min": spend_diff_int,
            "this_earn_total_min": this_earn_total_int,
            "earn_diff_min": earn_diff_int,
        },
        json_dumps_params={'ensure_ascii': False}
    )