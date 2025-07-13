# 배포 가이드

이 문서는 예규판례 모니터링 시스템의 다양한 배포 방법과 설정을 다룹니다.

## 목차
- [로컬 개발 환경](#로컬-개발-환경)
- [LocalTunnel 배포](#localtunnel-배포)
- [Fly.io 배포](#flyio-배포)
- [systemd 서비스 설정](#systemd-서비스-설정)

---

## 로컬 개발 환경

### 개발 서버 실행
```bash
./run.sh
# 또는
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload
```

## LocalTunnel 배포

### 개요
LocalTunnel은 로컬 서버를 인터넷에 노출시키는 터널링 서비스입니다. ngrok와 달리 고정 서브도메인을 무료로 제공하여 URL이 변경되지 않습니다.

### 장점
- **고정 URL**: `https://taxupdater-monitor.loca.lt` (절대 변경되지 않음)
- **완전 자동화**: 재부팅 후 자동으로 동일한 URL로 복구
- **북마크 가능**: URL이 고정이므로 브라우저 북마크 저장 가능
- **관리 불필요**: URL 확인, 복사, 모니터링 등 모든 번거로운 작업 제거

### 설치 및 설정
```bash
# LocalTunnel 전역 설치
npm install -g localtunnel

# 자동 설정 스크립트 실행
./scripts/setup/setup_localtunnel.sh
```

### 서비스 관리
```bash
# 상태 확인
systemctl --user status taxupdater localtunnel

# 재시작
systemctl --user restart taxupdater localtunnel

# 중지
systemctl --user stop taxupdater localtunnel

# 로그 확인
journalctl --user -u localtunnel -f
```

### 수동 실행 (디버깅용)
```bash
# 고정 서브도메인으로 실행
lt --port 8001 --subdomain taxupdater-monitor
```

## Fly.io 배포

### 개요
Fly.io는 컨테이너 기반의 글로벌 배포 플랫폼으로, 애플리케이션을 전 세계 여러 지역에 쉽게 배포할 수 있습니다.

### 배포 준비
1. **Fly CLI 설치**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **설정 파일**
   - 앱 설정: `deploy/fly.io/fly.toml`
   - Dockerfile: `deploy/fly.io/Dockerfile.fly`
   - 마이그레이션 확인: `deploy/fly.io/migration_check.py`

### 배포 과정
```bash
# Fly.io 로그인
fly auth login

# 앱 생성 (최초 1회)
fly apps create taxupdater-monitor

# 볼륨 생성 (데이터 영속성)
fly volumes create data --size 1 --region nrt

# 배포
fly deploy --config deploy/fly.io/fly.toml --dockerfile deploy/fly.io/Dockerfile.fly
```

### 배포 후 확인
```bash
# SSH 접속
fly ssh console

# 마이그레이션 상태 확인
python deploy/fly.io/migration_check.py

# 로그 확인
fly logs
```

### 문제 해결
- **500 에러 발생 시**: 모니터링 시스템 테이블 누락 가능성
- **해결 방법**: 자동 마이그레이션이 실행되도록 서버 재시작
- **수동 마이그레이션**: `python src/database/migrations.py`

## systemd 서비스 설정

### 개요
systemd를 사용하여 시스템 부팅 시 자동으로 서비스를 시작하고, 장애 발생 시 자동 재시작하도록 설정합니다.

### 자동화 아키텍처
```
부팅 시작
    ↓
systemd 사용자 서비스 자동 시작
    ↓
├── taxupdater.service (웹서버)
│   └── localhost:8001에서 서비스 실행
│
└── localtunnel.service (터널링)
    └── https://taxupdater-monitor.loca.lt로 고정 연결
    ↓
완전 자동화 완료 (사용자 개입 불필요)
```

### 설정 방법
```bash
# 자동 설정 스크립트 실행
./scripts/setup/setup_localtunnel.sh

# 또는 수동 설정
cp config/localtunnel.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable taxupdater localtunnel
systemctl --user start taxupdater localtunnel
```

### 서비스 파일 예시
```ini
# taxupdater.service
[Unit]
Description=Tax Updater Web Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/kibaek/claude-dev/taxupdater
ExecStart=/home/kibaek/claude-dev/taxupdater/taxupdater_venv/bin/python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

---

## 배포 방법 비교

| 방법 | 장점 | 단점 | 권장 사용 사례 |
|------|------|------|----------------|
| LocalTunnel | 고정 URL, 무료 | 로컬 PC 필요 | 개발/테스트 |
| Fly.io | 클라우드 기반 | 설정 복잡 | 프로덕션 |
| systemd | 완전 자동화 | 로컬 환경 한정 | 로컬 24/7 운영 |

---

## 관련 문서
- 기술적 세부사항: [TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)
- 문제 해결 가이드: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)