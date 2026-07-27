# 🧾 도파민 가계부 (Dopamine Ledger)

> **숏폼은 공짜가 아닙니다 — 벌어서 쓰세요.**
> 숏폼에 쓴 시간을 '지출'로, 독서·운동 같은 오프라인 활동을 '수입'으로 기록하는 주의력 가계부.

---

## 📌 프로젝트 소개

숏폼 과소비를 **막는(차단)** 대신 **보이게** 만들어, 사용자가 스스로 시간 소비를 조절하게 하는 서비스입니다.
가계부가 소비를 막지 않고도 소비를 바꿔온 원리를, 돈에서 시간으로 옮깁니다.

- 숏폼 사용 시간 → **지출** / 오프라인 활동 → **수입**
- 시간을 돈·책·운동량으로 **환산**해 체감
- 주간 예산 안에서 쓰되, 부족하면 활동으로 **벌어서** 사용
- 매일 밤 **하루 마감**, 일요일 **주간 결산**, 친구들과 **크루**로 서로의 잔액 공유

---

## 🛠 기술 스택

| 구분     | 기술                                       |
| -------- | ------------------------------------------ |
| Backend  | Python, Django (서버 렌더링), Django ORM   |
| Frontend | Django Template, HTML/CSS, Vanilla JS      |
| 인증     | Django Auth + django-allauth (소셜 로그인) |
| DB       | 개발: SQLite / 배포: PostgreSQL            |
| 이미지   | Pillow (공유 카드 생성)                    |
| 인프라   | Docker, docker-compose, Nginx, gunicorn    |
| 배포     | AWS (EC2 / Lightsail)                      |

> 원칙: **정규 세션에서 배운 스택 안에서 전 기능 구현.** 추가 학습은 allauth · AWS 세팅 · Pillow 셋으로 한정.

---

## 🚀 시작하기 (로컬 개발)

### 사전 요구사항

- Docker & Docker Compose 설치
- Git

### 실행 (3줄)

```bash
git clone https://github.com/<조직>/<레포>.git
cd dopamine-ledger
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

| 변수              | 설명               | 예시                           |
| ----------------- | ------------------ | ------------------------------ |
| `SECRET_KEY`      | Django 시크릿 키   | (랜덤 문자열)                  |
| `DEBUG`           | 디버그 모드        | `True` (개발) / `False` (배포) |
| `DATABASE_URL`    | DB 접속 정보       | 개발은 비워두면 SQLite         |
| `KAKAO_CLIENT_ID` | 카카오 소셜 로그인 | (발급값)                       |
| `KAKAO_SECRET`    | 카카오 시크릿      | (발급값)                       |

---

## 📁 프로젝트 구조

```
dopamine-ledger/
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
│   └── wsgi.py
├── accounts/               # 회원·온보딩·설정  (담당: 유채영)
├── ledger/                 # 지출·수입 기록, 환산  (담당: 정승현·정지민)
├── budget/                 # 예산·잔액·셀프 잠금·하루 마감  (2주차)
├── crew/                   # 크루·피드·공유 카드  (3주차)
├── templates/              # 공통 템플릿
├── static/                 # CSS·JS·이미지
└── deploy/                 # Nginx 설정 등 배포 관련
```

> 앱(폴더) 경계 = 기능 경계 = 담당자 경계. "이 코드 누가 짰지?"가 폴더만 봐도 보이게.

---

## 🗓 개발 로드맵 (4주)

| 주차      | 목표                                                       |
| --------- | ---------------------------------------------------------- |
| **0주차** | 배포 환경 세팅 (Docker·AWS·저장소)                         |
| **1주차** | 코어의 절반 — 로그인 → 온보딩 → 기록 → 환산                |
| **2주차** | 코어 완성 — 예산·잔액·하루 마감·셀프 잠금·주간 결산        |
| **3주차** | 소셜 + 마감 — 크루 피드·신용점수·공유 카드 → **베타 배포** |
| **4주차** | 베타 운영 & 실사용 데이터 수집                             |

---

## 👥 팀

| 이름   | 역할             |
| ------ | ---------------- |
| 강성훈 | PM · 인프라/배포 |
| 유채영 | 인증 · 온보딩    |
| 정승현 | 지출·수입 기록   |
| 정지민 | 환산 엔진        |
| 이지아 | 모델·기반        |

> 협업 규칙은 [CONTRIBUTING.md](./CONTRIBUTING.md) 참고.
