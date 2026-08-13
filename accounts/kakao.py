import requests
from django.conf import settings

def send_kakao_memo(user, text, link_url=None):
    """카카오톡 '나에게 보내기'로 메시지 전송.
    성공 True / 실패 False.
    """
    if not user.kakao_access_token:
        return False   # 카카오 연결 안 된 유저

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {user.kakao_access_token}"}

    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": link_url or "https://localhost:8000/ledger/",
            "mobile_web_url": link_url or "https://localhost:8000/ledger/",
        },
        "button_title": "확인하러 가기",
    }

    res = requests.post(
        url,
        headers=headers,
        data={"template_object": __import__("json").dumps(template)},
    )
    return res.status_code == 200

def refresh_kakao_token(user):
    """refresh_token으로 access_token 갱신. 성공 True."""
    if not user.kakao_refresh_token:
        return False

    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.KAKAO_REST_API_KEY,
            "refresh_token": user.kakao_refresh_token,
            "client_secret": settings.KAKAO_CLIENT_SECRET,
        },
    )
    if res.status_code != 200:
        return False

    data = res.json()
    user.kakao_access_token = data["access_token"]
    # 리프레시 토큰도 갱신될 때가 있음
    if "refresh_token" in data:
        user.kakao_refresh_token = data["refresh_token"]
    user.save(update_fields=['kakao_access_token', 'kakao_refresh_token'])
    return True

    res = requests.post(url, headers=headers, data={...})
    if res.status_code == 401:          # 토큰 만료
        if refresh_kakao_token(user):
            headers["Authorization"] = f"Bearer {user.kakao_access_token}"
            res = requests.post(url, headers=headers, data={...})
    return res.status_code == 200