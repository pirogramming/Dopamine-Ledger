# 🧾 도파민 가계부 (Dopamine Ledger)

> **숏폼은 공짜가 아닙니다 — 벌어서 쓰세요.**
> 숏폼에 쓴 시간을 '지출'로, 독서·운동 같은 오프라인 활동을 '수입'으로 기록하는 주의력 가계부.

---

## 📌 프로젝트 소개

숏폼 과소비를 **막는(차단)** 대신 **보이게** 만들어, 사용자가 스스로 시간 소비를 조절하게 하는 서비스입니다.
가계부가 소비를 막지 않고도 소비를 바꿔온 원리를, 돈에서 시간으로 옮깁니다.

- 숏폼 사용 시간 → **지출** / 독서·공부·운동 같은 오프라인 활동 → **수입**
- 시간을 사용자가 정한 단위(책·문제·운동 횟수·원 등)로 **환산**해 체감
- 주간 예산 안에서 쓰되, 부족하면 활동으로 **벌어서** 사용
- 매일 밤 **하루 마감**으로 연속 기록일을 쌓고, 일요일엔 **주간 결산**
- 연속 기록일에 따라 **리그 등급**이 오르며 환전 우대율 획득
- 친구들과 **크루**를 만들어 서로의 기록을 응원하고 잔액을 공유

---

## ✨ 핵심 기능

| 기능 | 설명 |
| --- | --- |
| 📝 기록 | 숏폼 사용 시간(지출), 독서·공부·운동 등 활동(수입)을 각각 기록 |
| 🔁 환산 | 사용자가 온보딩에서 정한 "1시간당 N개" 기준으로 시간을 원하는 단위(권·문제·회·원 등)로 환산 |
| 💰 예산·잔액 | 주간 예산 내에서 지출하고, 부족하면 활동으로 벌어서 사용. 잔액은 저장하지 않고 매번 ORM 집계로 계산해 정합성 문제를 원천 차단 |
| 🌙 하루 마감 | 매일 밤 하루를 마감하면 연속 기록일(streak)이 갱신됨 |
| 🏅 리그 시스템 | 연속 기록일에 따라 `도파민 노예 → 도파민 디톡서 → 시간 연금술사 → 도파민 정복자 → 절제의 신` 5단계로 승급, 등급이 오를수록 최대 +10% 환전 우대율 적용 |
| 📊 주간 결산 | 이번 주 수입/지출을 지난주와 비교해 요약하고, Pillow로 생성한 결산 공유 카드(PNG)를 다운로드 |
| 👥 크루 | 초대 코드로 친구를 초대(최대 6명), 3명 이상이면 크루 활성화. 목표 시간과 피드(벌이·과지출·응원·마감·탈퇴·강퇴)로 서로의 기록을 공유 |
| 🔐 카카오 로그인 | django-allauth 기반 카카오 소셜 로그인 및 계정 연동 |
| ❓ FAQ | 온보딩·홈·크루·마감·결산 화면별 도움말 제공 |

---

## 🛠 기술 스택

| 구분     | 기술                                                |
| -------- | --------------------------------------------------- |
| Backend  | Python, Django (서버 렌더링), Django ORM, Django REST Framework (온보딩 등 일부 API) |
| Frontend | Django Template, HTML/CSS, Vanilla JS                |
| 인증     | Django Auth + django-allauth (카카오 소셜 로그인)     |
| DB       | 개발: SQLite / 배포: PostgreSQL                       |
| 이미지   | Pillow (주간 결산 공유 카드 생성)                     |
| 인프라   | Docker, docker-compose, gunicorn                      |
| 배포     | AWS EC2 (GitHub Actions로 `develop` push 시 자동 배포) |

> 원칙: **정규 세션에서 배운 스택 안에서 전 기능 구현.** 추가 학습은 allauth · AWS 세팅 · Pillow 셋으로 한정.

---

## 🚀 시작하기 (로컬 개발)

### 사전 요구사항

- Docker & Docker Compose 설치
- Git

### 실행 (3줄)

```bash
git clone https://github.com/pirogramming/Dopamine-Ledger.git
cd Dopamine-Ledger
docker-compose up --build
```

브라우저에서 `http://localhost:8000` 접속.

### 최초 1회 세팅

```bash
# 컨테이너 안에서 마이그레이션
docker-compose exec web python manage.py migrate

# 관리자 계정 생성 (admin 페이지용)
docker-compose exec web python manage.py createsuperuser
```

### 환경 변수

`.env.example`을 복사해서 `.env`를 만들고 값을 채웁니다. (`.env`는 절대 커밋하지 않습니다 — `.gitignore`에 포함)

```bash
cp .env.example .env
```

| 변수                          | 설명                                       | 예시                                   |
| ----------------------------- | ------------------------------------------ | --------------------------------------- |
| `SECRET_KEY`                  | Django 시크릿 키                           | (랜덤 문자열 — 아래 명령으로 생성)      |
| `DEBUG`                       | 디버그 모드                                | `True` (개발) / `False` (배포)          |
| `ALLOWED_HOSTS`                | 접속 허용 호스트 (콤마 구분)               | `localhost,127.0.0.1`                   |
| `DATABASE_URL`                | DB 접속 정보 (비워두면 SQLite로 폴백)      | `postgres://dopamine:dopamine@db:5432/dopamine` |
| `POSTGRES_DB/USER/PASSWORD`   | docker-compose의 Postgres 컨테이너 초기값  | `dopamine` / `dopamine` / `dopamine`    |
| `KAKAO_REST_API_KEY`          | 카카오 소셜 로그인 REST API 키             | (카카오 개발자센터 발급값)              |
| `KAKAO_CLIENT_SECRET`         | 카카오 시크릿                              | (발급값)                                |
| `KAKAO_REDIRECT_URI`          | 카카오 로그인 콜백 URL                     | `http://localhost:8000/accounts/kakao/callback/` |
| `KAKAO_CONNECT_REDIRECT_URI`  | 기존 계정에 카카오 연동 시 콜백 URL        | `http://localhost:8000/accounts/kakao/connect/callback/` |
| `CSRF_TRUSTED_ORIGINS`        | (선택) 배포 도메인 CSRF 허용 목록 (콤마 구분) | `https://your-domain.com`             |

```bash
# SECRET_KEY 생성
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 테스트 실행

```bash
docker-compose exec web python manage.py test
```

---

## 📁 프로젝트 구조

```
Dopamine-Ledger/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── manage.py
├── config/                 # 프로젝트 설정
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py / wsgi.py
├── accounts/               # 회원가입·로그인·카카오 연동·온보딩·설정, 리그 등급 로직  (담당: 유채영)
├── ledger/                 # 지출·수입 기록, 환산, 하루 마감, 주간 결산·공유 카드, 리그 여정  (담당: 정승현·정지민)
├── budget/                 # 활동(Activity)·환산율 모델 — 자체 URL 없이 ledger·accounts에서 사용
├── crew/                   # 크루 생성·초대·피드·응원·목표  (담당: 강성훈)
├── templates/               # 전역 공통 템플릿 (base.html) — 각 앱은 자체 templates/도 보유
├── static/                  # 전역 정적 파일 (아이콘·캐릭터 이미지 등) — 각 앱은 자체 static/도 보유
└── .github/                 # 이슈 템플릿, PR 템플릿, 배포 워크플로우
```

> 앱(폴더) 경계 = 기능 경계 = 담당자 경계. "이 코드 누가 짰지?"가 폴더만 봐도 보이게.

---

## 🗓 개발 로드맵

| 주차      | 목표                                                       | 상태 |
| --------- | ------------------------------------------------------------ | :--: |
| **0주차** | 배포 환경 세팅 (Docker·AWS·저장소)                             | ✅ 완료 |
| **1주차** | 코어의 절반 — 로그인 → 온보딩 → 기록 → 환산                    | ✅ 완료 |
| **2주차** | 코어 완성 — 예산·잔액·하루 마감·셀프 잠금·주간 결산              | ✅ 완료 |
| **3주차** | 소셜 + 마감 — 리그 시스템·크루 피드·공유 카드 → **베타 배포**    | ✅ 완료 |
| **4주차** | 베타 운영 & 실사용 데이터 수집                                  | 🚧 진행중 |

---

## 👥 팀

| 이름   | 역할                                            |
| ------ | ----------------------------------------------- |
| 강성훈 | PM · 배포/인프라 · 크루                          |
| 유채영 | 인증 · 온보딩 · 신용등급 · 캐릭터                 |
| 이지아 | 모델 · 예산/잔액 · 공유 카드 · 프레임/크루 CSS     |
| 정지민 | 환산 엔진 · 하루 마감 · 결산 차트 · 홈 CSS         |
| 정승현 | 기록 CRUD · 활동 타이머 · 와이어프레임 · 디자인 총괄 |

> 협업 규칙은 [CONTRIBUTING.md](./CONTRIBUTING.md) 참고.
