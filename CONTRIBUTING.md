# 🤝 기여 가이드 (CONTRIBUTING)

도파민 가계부 팀의 협업 규칙입니다. **작업 시작 전에 꼭 읽어주세요.**

---

## 📢 소통

- **실시간 소통:** 디스코드
- **공지·문서:** 노션
- **정기 회의:** 매일 1회 (짧게 — 어제 한 것 / 오늘 할 것 / 막힌 것)
- **막히면:** 30분 이상 혼자 헤매지 말고 디스코드에 공유. 팀장이 지원합니다.

---

## 🌿 브랜치 전략

```
main        ← 배포용.
 └ develop  ← 통합 브랜치. feature가 여기로 머지됨. push 시 EC2에 자동 배포.
    └ feature/기능명   ← 개인 작업 브랜치. 이슈 단위로 생성.
```

- **`main` 직접 push 금지.** 모든 변경은 PR을 통해 들어옵니다.
- 작업은 항상 최신 `develop`에서 브랜치를 따서 시작합니다.
- `develop`에 머지(push)되면 GitHub Actions가 즉시 EC2에 자동 배포합니다 (`.github/workflows/deploy.yml`). **`develop`도 항상 실행 가능한 상태로 유지하세요.**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/onboarding-form
```

### 브랜치 이름 규칙

- `feature/기능명` — 새 기능 (예: `feature/expense-record`)
- `fix/버그명` — 버그 수정 (예: `fix/timer-reset`)
- `docs/문서명` — 문서 (예: `docs/readme`)

> **이슈 단위로 브랜치를 만듭니다.** 이슈 하나 = 브랜치 하나 = PR 하나.

---

## 🎫 이슈 관리

- **이슈는 작게 세분화합니다.** "온보딩 만들기"(X) → "온보딩 1단계: 환산 단위 선택 화면"(O)
- 이슈 하나는 **1~2일 안에 끝낼 수 있는 크기**로.
- 작업 시작 전 이슈를 먼저 만들고, 그 이슈 번호로 브랜치·PR을 연결합니다.

**이슈 제목 예시**

- `[accounts] 온보딩 - 시급/예산 설정 폼`
- `[ledger] 지출 기록 CRUD`
- `[ledger] 환산 함수 + 단위 테스트`

---

## ✍️ 커밋 컨벤션

`<타입>: <내용>` 형식으로 작성합니다.

| 타입       | 용도                       |
| ---------- | -------------------------- |
| `feat`     | 새 기능                    |
| `fix`      | 버그 수정                  |
| `docs`     | 문서                       |
| `style`    | 코드 포맷 (기능 변화 없음) |
| `refactor` | 리팩터링                   |
| `test`     | 테스트 추가/수정           |
| `chore`    | 설정·빌드 등 잡무          |

```bash
git commit -m "feat: 온보딩 시급 설정 폼 추가"
git commit -m "fix: 타이머 종료 시 적립분 계산 오류 수정"
```

---

## 🔀 Pull Request (PR)

1. 작업이 끝나면 `develop`을 대상으로 PR을 엽니다.
2. **최소 2명의 리뷰 승인** 후 머지합니다.
3. PR은 **이슈 단위**로 작게 유지합니다. (거대한 PR = 리뷰 지옥)
4. 리뷰어가 이해할 수 있도록 **핵심 로직엔 간단한 주석**을 답니다.

### PR 설명에 담을 것

- 무엇을 / 왜 바꿨는지 (2~3줄)
- 관련 이슈 번호 (`Closes #12`)
- 테스트 방법 (어떻게 확인했는지)
- (화면이면) 스크린샷

### 리뷰할 때

- 비난이 아니라 제안. "이거 왜 이렇게 했어요?"(X) → "여기 이렇게 하면 어떨까요?"(O)
- 사소한 것도 좋으니 **막힌 사람 없게 빨리 리뷰**합니다. 리뷰 대기가 병목이 되지 않도록.

---

## 🧪 코드 규칙

- **환산 엔진 등 핵심 로직은 단위 테스트를 붙입니다.** (숫자가 틀리면 서비스가 무너짐)
- 잔액 등 파생값은 저장하지 않고 ORM 집계로 계산합니다. (정합성 문제 원천 차단)
- `.env`, 시크릿 키, DB 파일 등은 **절대 커밋하지 않습니다.** (`.gitignore` 확인)
- 커밋 전 로컬에서 한 번 실행해보고 올립니다. (`docker-compose up`으로 안 깨지는지)

---

## ⚖️ 의사결정

- 논의는 함께, 하지만 **막히면 최종 결정은 PM(강성훈)이 책임지고 내립니다.**
- 방향성에서 벗어나지 않는 한, 각 담당자가 자기 파트의 세부는 자율적으로 결정합니다.

---

## 🆘 자주 쓰는 명령어

```bash
# 컨테이너 실행
docker-compose up

# 마이그레이션
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# 테스트 실행
docker-compose exec web python manage.py test

# 컨테이너 안 셸 접속
docker-compose exec web bash
```
