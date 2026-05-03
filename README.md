# 예규판례 모니터링 시스템

예규판례 자동 모니터링 시스템 - 주기적 크롤링, 새로운 데이터 탐지, 실시간 알림 기능을 갖춘 완전 자동화된 모니터링 플랫폼

## 기능

- 조세심판원 심판례 수집
- 국세법령정보시스템 유권해석 수집
- 국세법령정보시스템 판례 수집
- 기획재정부 해석 사례 수집
- 행정안전부 유권해석 수집
- 감사원 심사결정례 수집
- 주기적 자동 크롤링
- **웹 인터페이스 지원** (FastAPI 기반)

## 요구사항

- Python 3.7+
- Chrome/Chromium 브라우저
- ChromeDriver

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 웹 인터페이스 실행 (권장)
```bash
# 간단한 실행
./run.sh

# 수동 실행 (개발용)
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload

# 웹 인터페이스 접속
# 로컬: http://localhost:8001
# 외부: $NGROK_URL (ngrok Dev Domain 고정 URL)
```

### ngrok Dev Domain 터널 설정
```bash
# 고정 URL로 ngrok 실행
./scripts/setup/start_ngrok_dev_domain.sh

# 현재 외부 URL 확인
./scripts/setup/status_ngrok_dev_domain.sh

# 터널 중지
./scripts/setup/stop_ngrok_dev_domain.sh

# 로그인 시 ngrok 자동 시작 등록
./scripts/setup/install_ngrok_login_agent.sh

# 웹 서버 자동 실행 상태 확인
launchctl print gui/$(id -u)/taxupdater-web       # 웹 서버 상태 확인
```

## 최신 업데이트

### 🧹 프로젝트 정리 (2026.04.30)
- Docker/Railway/Fly 설정과 이전 테스트 파일 제거
- 현재 운영 경로는 FastAPI + SQLite + ngrok Dev Domain 터널링 중심으로 단순화
- 오래된 구현은 필요한 항목만 `archive/legacy/`에 보존

### 🚀 ngrok Dev Domain 고정 URL 운영
- **고정 URL**: `NGROK_URL`에 설정한 ngrok Dev Domain 사용
- **단순 운영**: 웹 서버는 macOS `launchctl`로 유지하고, 터널은 명령 하나로 실행
- **북마크 가능**: 회사 등 외부 네트워크에서 같은 URL로 접속
- **관리 단순화**: 설정 화면에서 현재 ngrok URL과 고정 URL 일치 여부 확인

### 📁 프로젝트 구조 정리 (2025.07.06)
- **체계적 분류**: 루트 디렉토리 파일들을 성격별로 분류 및 정리
- **ngrok 잔재 제거**: 11개의 불필요한 ngrok 관련 파일 삭제
- **직관적 구조**: docs/, scripts/, config/ 중심으로 정리
- **접근성 향상**: 관련 파일들의 논리적 그룹화로 유지보수성 개선

### 🎨 모니터링 시스템 완성 (2025.06.30 ~ 2025.07.02)
- **실시간 대시보드**: WebSocket 기반 실시간 모니터링 인터페이스
- **자동 스케줄링**: APScheduler 기반 주기적 자동 크롤링
- **스마트 알림**: 새로운 데이터 발견 시 즉시 알림
- **상세 통계**: 크롤링 과정의 완전한 투명성 제공
- **모바일 최적화**: 스마트폰에서도 완벽한 모니터링 가능

## 프로젝트 구조 (2025.07.06 정리 완료)

체계적으로 정리된 프로젝트 구조:

```
taxupdater/
├── start_web.py              # 웹서버 시작 파일  
├── requirements.txt          # 패키지 의존성
├── run.sh                    # 기본 실행 스크립트
├── CLAUDE.md                 # 프로젝트 가이드
├── README.md                 # 프로젝트 설명
├── docs/                     # 📋 개발 문서들
├── scripts/                  # 🔧 스크립트 파일들
│   ├── management/           # 시스템 관리 스크립트
│   └── setup/               # 환경 설정 스크립트
├── config/                  # ⚙️ 설정 파일들
├── src/                    # 소스 코드
│   ├── crawlers/           # 크롤러 클래스들
│   ├── services/           # 비즈니스 로직 서비스
│   ├── web/               # FastAPI 웹 애플리케이션
│   ├── repositories/      # 데이터 저장소 (SQLite, Excel)
│   └── config/            # 설정 관리
├── data/                  # 데이터베이스 및 백업
├── logs/                  # 로그 파일들
└── taxupdater_venv/       # 가상환경
```
