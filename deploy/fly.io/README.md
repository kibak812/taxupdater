# Fly.io 배포 가이드

예규판례 모니터링 시스템을 Fly.io에 배포하는 방법입니다.

## 📋 필요 파일

- `fly.toml` - Fly.io 애플리케이션 설정
- `Dockerfile.fly` - Fly.io 배포용 Docker 설정
- `Dockerfile` - 일반 Docker 설정 (백업)
- `migration_check.py` - 배포 후 데이터베이스 마이그레이션 확인 스크립트

## 🚀 배포 단계

### 1. Fly.io CLI 설치 및 로그인
```bash
# Fly.io CLI 설치
curl -L https://fly.io/install.sh | sh

# 로그인
fly auth login
```

### 2. 볼륨 생성 (데이터 영속성)
```bash
# 데이터 볼륨 생성 (1GB)
fly volumes create taxupdater_data --region sin --size 1
```

### 3. 애플리케이션 배포
```bash
# 프로젝트 루트에서 실행 (deploy/fly.io 폴더가 아닌!)
cd /path/to/taxupdater

# fly.toml 파일을 프로젝트 루트로 복사
cp deploy/fly.io/fly.toml .

# 배포 실행
fly deploy --dockerfile deploy/fly.io/Dockerfile.fly
```

### 4. 배포 후 확인
```bash
# 애플리케이션 접속
fly open

# 로그 확인
fly logs

# SSH 접속
fly ssh console

# 마이그레이션 확인 (SSH 접속 후)
python deploy/fly.io/migration_check.py
```

## ⚙️ 설정 정보

### 리전 및 리소스
- **리전**: sin (싱가포르)
- **메모리**: 1GB
- **CPU**: 1 vCPU (shared)
- **포트**: 8080 (내부), HTTPS (외부)

### 볼륨 마운트
- **소스**: taxupdater_data
- **마운트 지점**: /data
- **용량**: 1GB

### 자동 스케일링
- **최소 머신**: 0개 (비용 절약을 위해 자동 중지)
- **자동 시작**: 활성화
- **자동 중지**: 활성화

## 🔧 문제 해결

### 500 에러 발생 시
1. SSH로 접속하여 마이그레이션 확인
```bash
fly ssh console
python deploy/fly.io/migration_check.py
```

2. 로그에서 에러 확인
```bash
fly logs --app taxupdater
```

### 볼륨 문제 시
```bash
# 볼륨 목록 확인
fly volumes list

# 볼륨 상태 확인
fly volumes show taxupdater_data
```

### 배포 실패 시
```bash
# 기존 앱 삭제 후 재생성
fly apps destroy taxupdater
fly launch --dockerfile deploy/fly.io/Dockerfile.fly
```

## 📊 배포 후 접속 URL

배포 완료 후 다음 URL로 접속 가능:
- **애플리케이션**: https://taxupdater.fly.dev
- **모니터링 대시보드**: https://taxupdater.fly.dev/dashboard
- **설정**: https://taxupdater.fly.dev/settings

## 💡 참고사항

- Fly.io는 사용량 기반 과금이므로 자동 중지 기능 활용
- 볼륨은 데이터 영속성을 위해 반드시 필요
- Chrome/ChromeDriver가 포함되어 있어 크롤링 기능 정상 작동
- 환경에 따라 크롤링 성능이 로컬 대비 다를 수 있음