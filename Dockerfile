# Python 3.12 slim 이미지 기반
FROM python:3.12-slim

# 파이썬 출력 버퍼링 끄기 (로그 즉시 표시), pyc 파일 생성 안 함
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 작업 디렉토리
WORKDIR /app

# 시스템 패키지 (Pillow, psycopg 등에 필요할 수 있음)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 복사·설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 전체 복사
COPY . .

# gunicorn으로 실행 (배포). 개발은 docker-compose에서 runserver로 오버라이드
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]