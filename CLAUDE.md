# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
세금 법령 크롤링 시스템 - SQLite 기반 데이터 저장 및 FastAPI 웹 인터페이스 제공

## 핵심 개발 명령어

### 환경 설정
```bash
# 가상환경 활성화
source taxupdater_venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 웹 서버 실행
```bash
# 간단한 실행
./run.sh

# 수동 실행 (개발용)
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload

# 웹 인터페이스 접속
# http://localhost:8001
```

### CLI 실행
```bash
# 레거시 GUI 실행 
python example.py

# 기능 테스트
python test_functionality.py
```

### 데이터베이스 관리
```bash
# SQLite 데이터베이스 위치
data/tax_data.db

# 백업 파일 위치  
data/backups/
```

## 아키텍처 개요

### 계층형 구조 (Interface-driven Design)
- **인터페이스 계층** (`src/interfaces/`): 모든 컴포넌트가 구현해야 하는 추상 인터페이스
- **크롤러 계층** (`src/crawlers/`): 사이트별 데이터 수집 구현체
- **서비스 계층** (`src/services/`): 비즈니스 로직 및 오케스트레이션
- **저장소 계층** (`src/repositories/`): 데이터 영속성 (SQLite, Excel)
- **웹 계층** (`src/web/`): FastAPI 기반 REST API 및 UI

### 핵심 설계 패턴
1. **Strategy Pattern**: 크롤러별 다른 수집 전략
2. **Repository Pattern**: 저장소 추상화 (SQLite ↔ Excel 전환 가능)
3. **Observer Pattern**: WebSocket을 통한 실시간 진행률 업데이트
4. **Interface Segregation**: CrawlerInterface, DataRepositoryInterface, UIInterface

### 데이터 흐름 및 누적 저장 시스템
```
웹 UI → FastAPI → CrawlingService → Crawler → Repository → SQLite/Excel
                     ↓                    ↓           ↑
              WebSocket 실시간 피드백   중복 제거    자동 백업
                                    (SQL JOIN)   
                                        ↓
                                   누적 저장
                              (기존 데이터 유지)
```

#### 누적 저장 프로세스
1. **크롤링**: 사이트에서 최신 데이터 수집
2. **중복 탐지**: SQL JOIN으로 기존 DB와 비교
3. **신규 필터링**: 기존에 없는 데이터만 추출  
4. **증분 저장**: 기존 데이터 유지하면서 신규 데이터 추가
5. **자동 백업**: 신규 데이터를 Excel로 백업

## 주요 컴포넌트

### 크롤러 시스템
- **클래스 기반 크롤러**: `TaxTribunalCrawler`, `NTSAuthorityCrawler`, `NTSPrecedentCrawler` (Selenium 기반, BaseCrawler 상속)
- **웹 레거시 크롤러**: `web_legacy_crawlers.py` (기획재정부, 행정안전부, 감사원 - tkinter 의존성 제거)
- **크롤러 매핑**: `site_key` ↔ `choice` 번호 변환 (`src/web/app.py`)

### 데이터 저장소
- **SQLite Repository**: 고성능 SQL 기반 저장 및 중복 제거
- **스키마 자동 마이그레이션**: 기존 테이블에 `created_at`, `updated_at` 컬럼 자동 추가
- **안전한 데이터 로드**: 컬럼 존재 여부 확인 후 접근

### 웹 인터페이스
- **실시간 모니터링**: WebSocket을 통한 크롤링 진행률 실시간 업데이트
- **사이트별 대시보드**: 개별 사이트 데이터 조회, 검색, 페이지네이션
- **비동기 크롤링**: ThreadPoolExecutor를 통한 백그라운드 크롤링

## 설정 관리

### 사이트 설정 (`src/config/settings.py`)
```python
# 사이트별 URL 및 데이터 컬럼 정의
URLS = {...}
DATA_COLUMNS = {...}  
KEY_COLUMNS = {...}   # 중복 제거용 키 컬럼
```

### 크롤링 설정
```python
CRAWLING_CONFIG = {
    "max_pages": 20,
    "max_items": 5000,
    "retry_count": 3,
    "timeout": 10
}
```

## 중요한 기술적 고려사항

### SQLite 제약사항 회피
기존 데이터가 있는 테이블에 `DEFAULT CURRENT_TIMESTAMP` 컬럼 추가 시:
```python
# 실패: ALTER TABLE ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# 성공: ALTER TABLE ADD COLUMN created_at TIMESTAMP + UPDATE 문 사용
```

### WebSocket 진행률 업데이트
```python
# WebSocketProgress 객체는 .value 속성 사용
progress.value = percentage  # O
progress['value'] = percentage  # X (tkinter 방식)
```

### 크롤링 서비스 호출 방식
```python
# 개별 사이트: site_key → choice 변환 필요
site_to_choice_mapping = {
    "moef": "3", "bai": "6", ...
}

# 누적 저장 방식 (기존 데이터 유지하면서 신규 데이터 추가)
save_data(site_key, new_entries, is_incremental=True)
```

### 데이터 무결성 및 누적 저장 시스템
- **자동 백업**: 모든 신규 데이터는 Excel 파일로 자동 백업
- **누적 저장**: 기존 데이터를 유지하면서 신규 항목만 증분 저장
- **SQL 기반 중복 제거**: JOIN을 사용한 고성능 신규 데이터 탐지
- **데이터 손실 방지**: 모든 크롤러에서 일관된 누적 저장 방식 적용

## 개발 가이드라인
- 파일 수정 전 항상 Read 도구로 파일 내용 확인
- 500줄 초과 파일 발견 시 모듈화 검토  
- 커밋 메시지는 간결하게 작성
- 웹 전용 환경 (tkinter 의존성 완전 제거)
- 모든 데이터 접근 시 컬럼 존재 여부 확인