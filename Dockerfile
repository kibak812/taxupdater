# Railway 배포용 Dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# Chrome 설치 (Selenium용)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . .

# 데이터 디렉토리 (Railway Volume 마운트 포인트)
RUN mkdir -p /data/backups

# 환경변수 기본값
ENV DATABASE_PATH=/data/tax_data.db
ENV BACKUP_PATH=/data/backups
ENV PORT=8080

# 포트 노출
EXPOSE 8080

# 실행
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8080"]
