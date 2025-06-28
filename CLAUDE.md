# TaxUpdater 프로젝트 개발 가이드

## 프로젝트 개요
세금 법령 크롤링 시스템 - SQLite 기반 데이터 저장 및 FastAPI 웹 인터페이스 제공

## 실행 방법

### 웹 UI 서버 실행
```bash
# 간단한 실행
./run.sh

# 또는 수동 실행
source taxupdater_venv/bin/activate
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload
```

웹 인터페이스: http://localhost:8001

## 프로젝트 구조
- `src/web/app.py` - FastAPI 웹 서버
- `src/crawlers/` - 크롤러 모듈들
- `src/services/` - 크롤링 서비스
- `src/repositories/` - 데이터 저장소
- `data/tax_data.db` - SQLite 데이터베이스

## 개발 가이드라인
- 파일 수정 전 항상 Read 도구로 파일 내용 확인
- 500줄 초과 파일 발견 시 모듈화 검토
- 커밋 메시지는 간결하게 작성