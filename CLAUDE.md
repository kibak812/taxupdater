# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
세금 법령 자동 모니터링 시스템 - 주기적 크롤링, 새로운 데이터 탐지, 실시간 알림 기능을 갖춘 완전 자동화된 모니터링 플랫폼

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

### 행정안전부 크롤링 특이사항 (2025.06.28 수정)
행정안전부 사이트 접근 시 반드시 `upperMenuId` 파라미터가 필요:
```python
# 올바른 URL (필수!)
mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000"

# 잘못된 URL (로그인 페이지로 리다이렉트됨)
mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000"
```

#### HTML 구조 (행정안전부)
```html
<ul class="search_out exp">
    <li>
        <p><span class="part">세목</span>문서번호 (날짜)</p>
        <p class="tt"><a onclick="authoritativePopUp(번호)">제목</a></p>
        <p class="txt"><a>내용요약</a></p>
    </li>
</ul>
```

#### 데이터 추출 로직
```python
# 1. 세목 추출
tax_category = item.find_element(By.CSS_SELECTOR, "span.part").text.strip()

# 2. 날짜 패턴 매칭
date_pattern = r'\((\d{4}\.\d{2}\.\d{2})\)'
date_match = re.search(date_pattern, first_p_text)

# 3. 문서번호 추출 (세목 제거 후)
doc_number = before_date.replace(tax_category, "").strip()

# 4. 링크 추출 (authoritativePopUp 함수에서 번호 추출)
popup_match = re.search(r'authoritativePopUp\((\d+)\)', onclick_attr)
link = f"https://www.olta.re.kr/explainInfo/authoInterpretationDetail.do?num={doc_id}"
```

### 감사원 크롤링 특이사항 (2025.06.29 수정)
감사원 청구분야 드롭다운 및 검색 로직:
```python
# 올바른 청구분야 값
claim_types = [
    {"name": "국세", "value": "10"},
    {"name": "지방세", "value": "20"}
]

# 드롭다운 선택 후 검색 버튼 클릭 필요
select_element = driver.find_element(By.CSS_SELECTOR, "select#reqDvsnCd")
select = Select(select_element)
select.select_by_value(claim_type["value"])

search_button = driver.find_element(By.CSS_SELECTOR, "div.searchForm button[type='button']")
driver.execute_script("arguments[0].click();", search_button)
```

#### 감사원 크롤링 범위
- **국세**: 5페이지
- **지방세**: 5페이지
- **총 10페이지**: 약 100개 항목 수집

### SQLite UNIQUE Constraint 해결 (2025.06.29)
PRIMARY KEY 충돌 시 자동 INSERT OR IGNORE 처리:
```python
# save_data 메서드에서 UNIQUE constraint 에러 발생 시
try:
    new_entries.to_sql(table_name, conn, if_exists='append', index=False, method='multi')
except sqlite3.IntegrityError:
    # INSERT OR IGNORE 방식으로 개별 처리
    self._insert_with_ignore(conn, table_name, new_entries, key_column)
```

### 데이터 무결성 및 누적 저장 시스템
- **자동 백업**: 모든 신규 데이터는 Excel 파일로 자동 백업
- **누적 저장**: 기존 데이터를 유지하면서 신규 항목만 증분 저장
- **SQL 기반 중복 제거**: JOIN을 사용한 고성능 신규 데이터 탐지
- **UNIQUE 제약 처리**: INSERT OR IGNORE를 통한 안전한 데이터 삽입
- **데이터 손실 방지**: 모든 크롤러에서 일관된 누적 저장 방식 적용

## 크롤링 시스템 현황 (2025.06.29)

### ✅ 완료된 크롤러
1. **조세심판원**: Selenium 기반 클래스 크롤러
2. **국세법령정보시스템 (유권해석)**: Selenium 기반 클래스 크롤러
3. **국세법령정보시스템 (판례)**: Selenium 기반 클래스 크롤러
4. **기획재정부**: 웹 레거시 크롤러 (tkinter 의존성 제거)
5. **행정안전부**: 웹 레거시 크롤러 (upperMenuId 파라미터 필수)
6. **감사원**: 웹 레거시 크롤러 (드롭다운 선택 + 검색 로직)

### 🌐 웹 인터페이스 완료
- **실시간 크롤링**: WebSocket 진행률 업데이트
- **사이트별 대시보드**: 개별 데이터 조회 및 검색
- **백그라운드 크롤링**: ThreadPoolExecutor 기반
- **자동 백업**: 신규 데이터 Excel 백업
- **중복 제거**: SQL JOIN 기반 고성능 처리
- **전체 크롤링**: `/api/crawl/all` 엔드포인트 통한 모든 사이트 일괄 크롤링

## 개발 가이드라인
- 파일 수정 전 항상 Read 도구로 파일 내용 확인
- 500줄 초과 파일 발견 시 모듈화 검토  
- 커밋 메시지는 간결하게 작성
- 웹 전용 환경 (tkinter 의존성 완전 제거)
- 모든 데이터 접근 시 컬럼 존재 여부 확인
- UNIQUE constraint 에러 시 INSERT OR IGNORE 처리

## 최신 개발 현황 (2025.06.29)

### 🔧 버그 수정 및 개선사항
1. **심판원 크롤링 로그 중복 제거**: 크롤러와 WebSocket 상태 로그 중복 방지
2. **WebSocketProgress 에러 해결**: `progress['value']` → `progress.value` 수정
3. **전체 크롤링 API 경로 매칭 수정**: `/api/crawl/all`을 `/api/crawl/{site_key}` 앞에 정의하여 올바른 매칭 보장
4. **WebSocket 연결 상태 표시 수정**: `window.app` 전역 노출로 실시간 연결 상태 정확히 표시

### 🚀 전체 크롤링 시스템 완성
- **FastAPI 경로 순서 최적화**: 구체적인 경로(`/api/crawl/all`)를 와일드카드 경로(`/api/crawl/{site_key}`) 앞에 배치
- **백그라운드 비동기 실행**: `asyncio.create_task()`를 통한 논블로킹 전체 크롤링
- **WebSocket 실시간 피드백**: 전체 크롤링 시작/완료/에러 상태 실시간 전송
- **ThreadPoolExecutor 활용**: 동기 크롤링 서비스를 비동기 환경에서 안전하게 실행

### 🎯 핵심 기술적 해결책
```python
# FastAPI 경로 정의 순서 (중요!)
@app.post("/api/crawl/all")        # 구체적 경로 먼저
async def start_all_crawling(): ...

@app.post("/api/crawl/{site_key}") # 와일드카드 경로 나중
async def start_crawling(): ...

# WebSocket 진행률 업데이트 방식
progress.value = percentage        # ✅ 올바른 방식
progress['value'] = percentage     # ❌ 잘못된 방식 (tkinter 스타일)

# 전체 크롤링 실행 로직
crawling_service.execute_crawling("7", None, None, is_periodic=False)

# WebSocket 연결 상태 표시 해결책
window.app = app;  # TaxCrawlerApp 인스턴스를 전역으로 노출
```

### ⚡ WebSocket 연결 상태 표시 문제 해결 (2025.06.29)
**문제**: 웹 페이지 하단에 "🔌 실시간 연결 상태: 연결 끊어짐 ❌" 표시
**원인**: HTML의 연결 상태 체크 코드에서 `window.app` 객체에 접근할 수 없음
**해결책**: `main.js`에서 TaxCrawlerApp 인스턴스를 전역으로 노출

```javascript
// src/web/static/js/main.js:543
document.addEventListener('DOMContentLoaded', () => {
    app = new TaxCrawlerApp();
    window.app = app; // 전역으로 노출하여 HTML에서 접근 가능
});
```

## 🚀 주요 업데이트 (2025.06.30): 자동 모니터링 시스템 완성

### 📋 새로운 기능
1. **주기적 자동 크롤링**: APScheduler 기반 백그라운드 스케줄링
2. **새로운 데이터 탐지**: 실시간 새로운 데이터 발견 및 로깅
3. **실시간 알림 시스템**: WebSocket 기반 즉시 알림
4. **모니터링 중심 UI**: 새로운 데이터 중심의 대시보드

### 🗃️ 새로운 데이터베이스 테이블
- **`crawl_schedules`**: 사이트별 크롤링 스케줄 관리
- **`notification_history`**: 알림 이력 및 상태 관리
- **`new_data_log`**: 새로운 데이터 발견 로그
- **`system_status`**: 시스템 건강도 및 상태 모니터링

### 🔧 새로운 백엔드 시스템
- **SchedulerService**: APScheduler 기반 주기적 크롤링
- **NotificationService**: 다중 채널 알림 발송
- **자동 데이터 로깅**: 새로운 데이터 자동 태깅 및 분류

### 🎨 새로운 프론트엔드
- **모니터링 대시보드** (`/`): 새로운 모니터링 중심 UI
- **레거시 대시보드** (`/legacy`): 기존 수동 크롤링 UI
- **탭 기반 네비게이션**: 모니터링/스케줄/알림/시스템 상태
- **실시간 업데이트**: WebSocket 기반 실시간 데이터 갱신

### 📡 새로운 API 엔드포인트
```
GET    /api/schedules              - 스케줄 목록 조회
POST   /api/schedules              - 스케줄 생성/수정
DELETE /api/schedules/{site_key}   - 스케줄 삭제
POST   /api/schedules/{site_key}/trigger - 수동 크롤링 트리거

GET    /api/notifications          - 알림 목록 조회
POST   /api/notifications/{id}/read - 알림 읽음 처리
GET    /api/notifications/stats    - 알림 통계

GET    /api/new-data               - 새로운 데이터 조회
GET    /api/system-status          - 시스템 상태 조회
GET    /api/job-history            - 작업 이력 조회

POST   /api/scheduler/start        - 스케줄러 시작
POST   /api/scheduler/stop         - 스케줄러 중지
```

### 🎯 핵심 워크플로우
1. **자동 스케줄링**: 사이트별 설정된 주기에 따라 자동 크롤링
2. **새로운 데이터 탐지**: 크롤링 결과와 기존 데이터 비교하여 신규 데이터 식별
3. **즉시 알림**: 새로운 데이터 발견 시 WebSocket을 통한 실시간 알림
4. **상세 로깅**: 모든 새로운 데이터를 태그와 메타데이터와 함께 로깅
5. **시스템 모니터링**: 크롤러 상태, 성공률, 응답시간 등 종합 모니터링

### 🔄 마이그레이션 가이드
```bash
# 1. 의존성 업데이트
pip install -r requirements.txt

# 2. 데이터베이스 마이그레이션 실행
python src/database/migrations.py

# 3. 새로운 모니터링 시스템 접속
# http://localhost:8001 (새로운 모니터링 UI)
# http://localhost:8001/legacy (기존 수동 크롤링 UI)
```

### ⚙️ 주요 설정
- **기본 스케줄**: 각 사이트마다 6-12시간 간격으로 자동 크롤링
- **알림 임계값**: 새로운 데이터 1개 이상 발견 시 알림
- **자동 백업**: 신규 데이터 Excel 백업 유지
- **실시간 연결**: WebSocket 자동 재연결 지원

이제 세금 법령 크롤링 시스템이 **완전 자동화된 모니터링 플랫폼**으로 진화했습니다. 수동 크롤링에서 벗어나 24/7 자동 모니터링을 통해 새로운 법령과 해석을 놓치지 않고 적시에 탐지할 수 있습니다.

## 🎨 UI 현대화 및 한국어화 완료 (2025.06.30)

### 📱 새로운 프리미엄 UI 디자인
- **모던 인터페이스**: Inter 폰트, 프로페셔널 컬러 스킴, SVG 아이콘 사용
- **전문가 중심 설계**: 세무 전문가가 10초 내에 시스템 상태 파악 가능
- **반응형 디자인**: 데스크톱과 모바일 모두 지원
- **이모지 제거**: 비즈니스 환경에 적합한 프로페셔널 디자인

### 🚀 새로운 대시보드 기능
- **시간 필터**: 최근 24시간/3일/7일 + 사용자 정의 날짜 범위
- **상태 카드**: 사이트별 신규 데이터 건수를 중앙에 크게 표시
- **실시간 타임라인**: WebSocket 기반 최신 업데이트 실시간 표시
- **원클릭 데이터 접근**: 카드 클릭으로 해당 사이트 데이터 즉시 조회

### 📊 전문가용 데이터 테이블
- **고급 검색**: 문서번호, 제목, 내용 통합 검색
- **동적 정렬**: 모든 컬럼별 오름차순/내림차순 정렬
- **스마트 페이지네이션**: 대용량 데이터 효율적 탐색
- **원클릭 내보내기**: CSV 형태로 데이터 즉시 다운로드
- **실시간 새로고침**: 최신 데이터 실시간 반영

### ⚙️ 직관적인 설정 인터페이스
- **토글 기반 제어**: 사이트별 모니터링 간편 활성화/비활성화
- **스케줄러 상태**: 실시간 스케줄러 동작 상태 및 제어
- **알림 설정**: 실시간 알림 임계치 및 방식 설정
- **시스템 모니터링**: 각 크롤러의 다음 실행 시간 표시

### 🌐 완전 한국어화
- **UI 텍스트**: 모든 사용자 인터페이스 요소 한국어 변환
- **에러 메시지**: Toast 알림 및 오류 메시지 한국어화
- **기관명**: 영문 기관명을 한국어 정식 명칭으로 변경
  - Tax Tribunal → 조세심판원
  - NTS Authority → 국세청(유권해석) 
  - NTS Precedent → 국세청(판례)
  - Ministry of Economy → 기획재정부
  - Ministry of Interior → 행정안전부
  - Board of Audit → 감사원
- **상태 메시지**: 스케줄러 상태, 버튼 텍스트 등 모든 동적 메시지 한국어화

### 🔧 기술적 개선사항
- **CSS 변수 시스템**: 일관된 디자인 토큰 및 테마 관리
- **모듈화된 JavaScript**: 클래스 기반 컴포넌트 아키텍처
- **성능 최적화**: 디바운싱된 검색, 효율적인 페이지네이션
- **접근성 향상**: 키보드 네비게이션, 명확한 상태 표시

### 📍 새로운 경로 구조
```
/ (또는 /dashboard)     - 새로운 모니터링 대시보드
/data/{site_key}        - 사이트별 데이터 테이블 뷰
/settings               - 시스템 설정 및 스케줄 관리
/legacy                 - 기존 수동 크롤링 인터페이스
```

### 🎯 사용자 경험 향상
- **10초 규칙**: 전문가가 10초 내에 모든 중요 정보 파악 가능
- **원클릭 액세스**: 상태 카드에서 데이터까지 클릭 한 번으로 이동
- **실시간 피드백**: WebSocket을 통한 즉시 상태 업데이트
- **컨텍스트 보존**: 브레드크럼과 직관적인 네비게이션

이번 업데이트로 세금법령 모니터링 시스템이 **전문가급 비즈니스 도구**로 완전히 변모했습니다. 복잡한 데이터를 직관적으로 표시하고, 한국어 환경에서 완벽하게 동작하며, 모던한 웹 표준을 준수하는 프리미엄 인터페이스를 제공합니다.

## 🎯 스마트 데이터 필터링 시스템 (2025.07.01)

### 📋 직관적인 데이터 접근 방식
대시보드에서 데이터를 조회하는 두 가지 방법이 다른 결과를 제공합니다:

1. **상태 카드 클릭**: 선택된 시간 필터 기간의 **신규 데이터만** 표시
   - 카드에 표시된 숫자(예: "+15")와 일치하는 데이터 제공
   - 최근 24시간/3일/7일 또는 사용자 정의 기간의 신규 데이터만 조회
   
2. **"데이터 보기" 버튼 클릭**: 해당 사이트의 **전체 데이터** 표시
   - 시간 제한 없이 모든 수집된 데이터 조회
   - 전체 데이터셋에서 검색 및 분석 가능

### 🔧 구현된 기술적 요소

#### URL 파라미터 구조
```
/data/{site_key}?filter=recent&days=3       # 최근 3일 신규 데이터
/data/{site_key}?filter=recent&days=7       # 최근 7일 신규 데이터
/data/{site_key}?filter=range&start=2024-01-01&end=2024-01-31  # 날짜 범위
/data/{site_key}                            # 전체 데이터 (필터 없음)
```

#### Repository 시간 필터링 메서드
새로 추가된 `load_filtered_data()` 메서드:
- SQLite의 datetime 함수를 활용한 효율적인 쿼리
- `created_at` 또는 `updated_at` 컬럼 기반 필터링
- 시간 컬럼이 없는 경우 전체 데이터 반환 (하위 호환성)

#### 데이터 테이블 UI 개선
- 필터 상태에 따른 동적 제목 변경
- "최근 3일 신규 데이터" vs "전체 데이터" 명확히 구분
- 필터가 적용된 경우 "전체 데이터 보기" 링크 제공
- 브레드크럼과 필터 정보로 현재 상태 명확히 표시

### 🎨 사용자 경험 개선
- **일관성**: 카드에서 보는 숫자와 클릭 시 보는 데이터 일치
- **유연성**: 신규 데이터만 보거나 전체 데이터를 선택적으로 조회
- **편의성**: 필터된 뷰에서 전체 데이터로 한 번에 전환 가능
- **명확성**: 현재 보고 있는 데이터의 범위를 항상 명확히 표시

이 업데이트로 세금 전문가들이 필요에 따라 최신 변경사항만 빠르게 확인하거나 전체 데이터를 종합적으로 분석할 수 있는 유연한 시스템이 구축되었습니다.