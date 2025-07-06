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
# 외부: https://taxupdater-monitor.loca.lt (고정 URL)
```

### LocalTunnel 자동 배포 설정
```bash
# LocalTunnel 자동 설정 (한 번만 실행)
./scripts/setup/setup_localtunnel.sh

# 서비스 관리
systemctl --user status taxupdater localtunnel    # 상태 확인
systemctl --user restart taxupdater localtunnel   # 재시작
systemctl --user stop taxupdater localtunnel      # 중지
```

### CLI 실행 (레거시)
```bash
# 예제 실행
python scripts/examples/example.py

# 기능 테스트
python tests/test_functionality.py
```

## 최신 업데이트

### 🚀 LocalTunnel 완전 자동화 시스템 (2025.07.07)
- **고정 URL**: `https://taxupdater-monitor.loca.lt` (절대 변경되지 않음)
- **완전 자동화**: 재부팅 후 자동으로 동일한 URL로 복구
- **북마크 가능**: URL이 고정이므로 브라우저 북마크 저장 가능
- **관리 불필요**: URL 확인, 복사, 모니터링 등 모든 번거로운 작업 제거

### 📁 프로젝트 구조 정리 (2025.07.06)
- **체계적 분류**: 루트 디렉토리 파일들을 성격별로 분류 및 정리
- **ngrok 잔재 제거**: 11개의 불필요한 ngrok 관련 파일 삭제
- **직관적 구조**: docs/, scripts/, tests/, config/, deploy/ 디렉토리 신설
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
├── main.py                    # 메인 실행 파일
├── start_web.py              # 웹서버 시작 파일  
├── requirements.txt          # 패키지 의존성
├── run.sh                    # 기본 실행 스크립트
├── CLAUDE.md                 # 프로젝트 가이드
├── README.md                 # 프로젝트 설명
├── docs/                     # 📋 개발 문서들
├── scripts/                  # 🔧 스크립트 파일들
│   ├── management/           # 시스템 관리 스크립트
│   ├── examples/            # 예제/데모 스크립트  
│   └── setup/               # 환경 설정 스크립트
├── tests/                   # 🧪 테스트 파일들
├── config/                  # ⚙️ 설정 파일들
├── deploy/                  # 🚀 배포 관련 파일들
│   └── fly.io/             # Fly.io 배포 설정
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