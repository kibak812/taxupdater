# 배포 가이드

이 문서는 예규판례 모니터링 시스템의 다양한 배포 방법과 설정을 다룹니다.

## 목차
- [로컬 개발 환경](#로컬-개발-환경)
- [LocalTunnel 배포](#localtunnel-배포)
- [ngrok 배포](#ngrok-배포)
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

## ngrok 배포

### 개요
ngrok은 임시 외부 접속 URL이 필요할 때 사용하는 터널링 옵션입니다.
고정 URL 운영은 LocalTunnel을 우선 사용하고, 임시 공유나 백업 접속 경로가 필요할 때 ngrok을 사용합니다.

### 설정
```bash
./setup_ngrok.sh
./get_ngrok_url.sh
```

### 서비스 관리
```bash
systemctl --user status ngrok
systemctl --user restart ngrok
systemctl --user stop ngrok
```

## systemd 서비스 설정

### 개요
systemd를 사용하여 시스템 부팅 시 자동으로 서비스를 시작하고, 장애 발생 시 자동 재시작하도록 설정합니다.

### 자동화 아키텍처
```
부팅 시작
    |
systemd 사용자 서비스 자동 시작
    |
+-- taxupdater.service (웹서버)
|   +-- localhost:8001에서 서비스 실행
|
+-- localtunnel.service (터널링)
    +-- https://taxupdater-monitor.loca.lt로 고정 연결
    |
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
| ngrok | 임시 공유 쉬움 | 무료 URL 변동 | 임시 외부 접속 |
| systemd | 완전 자동화 | 로컬 환경 한정 | 로컬 24/7 운영 |

---

## 관련 문서
- 기술적 세부사항: [TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)
- 문제 해결 가이드: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)
