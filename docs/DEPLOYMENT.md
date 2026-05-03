# 배포 가이드

이 문서는 예규판례 모니터링 시스템의 다양한 배포 방법과 설정을 다룹니다.

## 목차
- [로컬 개발 환경](#로컬-개발-환경)
- [ngrok Dev Domain 배포](#ngrok-dev-domain-배포)

---

## 로컬 개발 환경

### 개발 서버 실행
```bash
./run.sh
# 또는
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload
```

## ngrok Dev Domain 배포

### 개요
ngrok Dev Domain은 ngrok 계정에 연결된 고정 URL입니다.
집 Mac에서 웹 서버를 계속 실행해두고 회사 등 외부에서 같은 URL로 접속하는 운영 경로로 사용합니다.

### 설정
```bash
# 고정 Dev Domain으로 ngrok 실행
./scripts/setup/start_ngrok_dev_domain.sh

# 현재 URL 확인
./scripts/setup/status_ngrok_dev_domain.sh

# 중지
./scripts/setup/stop_ngrok_dev_domain.sh

# 로그인 시 ngrok 자동 시작 등록
./scripts/setup/install_ngrok_login_agent.sh
```

### 서비스 관리
```bash
launchctl print gui/$(id -u)/taxupdater-web  # 웹 서버 자동 실행 상태
```

---

## 배포 방법 비교

| 방법 | 장점 | 단점 | 권장 사용 사례 |
|------|------|------|----------------|
| ngrok Dev Domain | 도메인 구매 없이 고정 URL | ngrok 계정 필요 | 현재 권장 운영 |
| Cloudflare Tunnel | 고정 도메인 + Access 보호에 강함 | 자체 도메인 필요 | 향후 도메인 구매 후 운영 |
| ngrok 임시 URL | 빠른 공유 | URL 변동 | 임시 테스트 |

---

## 관련 문서
- 기술적 세부사항: [TECHNICAL_DETAILS.md](./TECHNICAL_DETAILS.md)
- 문제 해결 가이드: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)
