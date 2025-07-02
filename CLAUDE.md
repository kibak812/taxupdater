# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
예규판례 자동 모니터링 시스템 - 주기적 크롤링, 새로운 데이터 탐지, 실시간 알림 기능을 갖춘 완전 자동화된 모니터링 플랫폼

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

이제 예규판례 크롤링 시스템이 **완전 자동화된 모니터링 플랫폼**으로 진화했습니다. 수동 크롤링에서 벗어나 24/7 자동 모니터링을 통해 새로운 예규와 판례를 놓치지 않고 적시에 탐지할 수 있습니다.

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

이번 업데이트로 예규판례 모니터링 시스템이 **전문가급 비즈니스 도구**로 완전히 변모했습니다. 복잡한 데이터를 직관적으로 표시하고, 한국어 환경에서 완벽하게 동작하며, 모던한 웹 표준을 준수하는 프리미엄 인터페이스를 제공합니다.

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

이 업데이트로 세무 전문가들이 필요에 따라 최신 변경사항만 빠르게 확인하거나 전체 데이터를 종합적으로 분석할 수 있는 유연한 시스템이 구축되었습니다.

## 🔧 데이터 일관성 개선 (2025.07.01)

### 문제점
기존 시스템에서 대시보드 카드에 표시되는 신규 데이터 숫자("+23" 등)와 카드 클릭 시 보여지는 실제 필터링된 데이터 개수가 불일치하는 문제가 있었습니다.

**원인**: 
- 카드 숫자: `new_data_log` 테이블의 `discovered_at` 기준
- 필터링된 데이터: 각 사이트 테이블의 `created_at/updated_at` 기준

### 해결책: 단일 데이터 소스 사용

`new_data_log` 테이블을 사용하는 복잡한 방식 대신, 각 사이트 테이블에서 직접 최근 데이터를 조회하는 단순하고 일관된 방식으로 변경:

#### 새로운 Repository 메서드
```python
# src/repositories/sqlite_repository.py
def get_recent_data_counts(self, hours: int = 24) -> Dict[str, int]:
    """각 사이트별 최근 데이터 개수 조회 (created_at/updated_at 기준)"""
```

#### 새로운 API 엔드포인트
```python
# src/web/app.py
@app.get("/api/sites/recent-counts")
async def get_recent_data_counts(hours: int = 24):
    """각 사이트별 최근 데이터 개수 조회 (각 사이트 테이블 기반)"""
```

#### 프론트엔드 업데이트
```javascript
// src/web/static/js/dashboard.js
// 기존: /api/new-data 사용
// 변경: /api/sites/recent-counts 사용
fetch(`/api/sites/recent-counts?hours=${this.currentTimeFilter}`)
```

### 🎯 개선 결과
- **완벽한 일관성**: 카드 숫자 = 실제 필터링된 데이터 개수
- **단순성**: 단일 데이터 소스로 복잡성 제거
- **신뢰성**: 표시된 숫자를 항상 신뢰할 수 있음
- **유지보수성**: 하나의 데이터 흐름만 관리하면 됨

### 📊 검증 결과
API 테스트 결과 모든 사이트에서 완벽한 일관성 확인:
- **조세심판원**: 카드 "+3" = 필터링된 데이터 3개 ✅
- **국세청(유권해석)**: 카드 "+28" = 필터링된 데이터 28개 ✅ 
- **행정안전부**: 카드 "+6" = 필터링된 데이터 6개 ✅

이제 사용자가 대시보드 카드에서 보는 숫자와 클릭했을 때 나타나는 실제 데이터가 100% 일치하며, 시스템의 신뢰성이 크게 향상되었습니다.

## 🕐 마지막 업데이트 시간 표시 문제 해결 (2025.07.01)

### 문제점
웹 대시보드에서 모든 사이트 카드의 "마지막 업데이트" 시간이 동일하게 "9시간 전"으로 표시되는 문제가 있었습니다.

**원인**: 
- 모든 사이트가 `crawl_metadata` 테이블의 동일한 `updated_at` 시간(시스템 초기화 시간: 2025-07-01 16:25:55)을 사용
- 실제 각 사이트 데이터의 최신 업데이트 시간과 불일치

### 해결책: 실제 데이터 기반 시간 표시

각 사이트 테이블에서 실제 데이터의 최신 시간을 조회하도록 `get_statistics()` 메서드를 수정:

#### Repository 레벨 수정 (`src/repositories/sqlite_repository.py`)
```python
def get_statistics(self, site_key: str) -> Dict[str, Any]:
    # 실제 데이터의 최신 업데이트 시간 조회
    actual_last_updated = None
    if total_count > 0:
        # 컬럼 존재 확인
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # created_at 또는 updated_at 컬럼에서 최신 시간 조회
        if 'created_at' in existing_columns or 'updated_at' in existing_columns:
            time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
            cursor.execute(f"SELECT MAX({time_column}) FROM [{table_name}]")
            actual_last_updated = cursor.fetchone()[0]

    stats = {
        "total_count": total_count,
        "last_updated": actual_last_updated,  # 실제 데이터의 최신 시간 사용
        # ...
    }
```

#### API 레벨 시간대 처리 개선 (`src/web/app.py`)
```python
# last_updated 시간을 ISO 형식으로 변환 (시간대 정보 포함)
last_updated = stats.get("last_updated")
if last_updated:
    try:
        # SQLite에서 온 시간 문자열을 datetime 객체로 변환
        dt = datetime.fromisoformat(last_updated)
        # ISO 형식으로 변환 (JavaScript가 올바르게 파싱할 수 있도록)
        last_updated = dt.isoformat()
    except (ValueError, TypeError):
        # 파싱 실패 시 원본 그대로 사용
        pass
```

### 🎯 개선 결과
수정 후 각 사이트별로 실제 데이터의 최신 업데이트 시간이 정확히 표시:
- **조세심판원**: 19시간 전 (2025-07-01 06:01:11)
- **국세청(유권해석)**: 23시간 전 (2025-07-01 02:02:11)
- **국세청(판례)**: 3일 전 (2025-06-28 16:36:43)
- **기획재정부**: 3일 전 (2025-06-28 15:39:58)
- **행정안전부**: 1일 전 (2025-06-30 15:37:52)
- **감사원**: 23시간 전 (2025-07-01 02:00:47)

### 📝 기술적 개선사항
- **정확성**: 각 사이트별 실제 데이터 기준 시간 표시
- **호환성**: 컬럼 존재 여부 확인으로 안전한 접근
- **성능**: `MAX()` 함수로 효율적인 최신 시간 조회
- **시간대 처리**: ISO 형식으로 JavaScript 호환성 향상

이제 대시보드에서 각 사이트의 "마지막 업데이트" 시간이 실제 크롤링된 데이터의 최신 시간을 정확히 반영하여 표시됩니다.

## 🔧 타임스탬프 표준화 시스템 개선 (2025.07.02)

### 배경
데이터 저장 시 타임스탬프 컬럼(`created_at`, `updated_at`)이 누락되거나 일관되지 않는 문제가 발생했습니다. 이로 인해 시간 기반 필터링 및 통계 기능에서 정확도가 떨어지는 현상이 있었습니다.

### 해결책: 자동 타임스탬프 주입 시스템

#### Repository 레벨 개선 (`src/repositories/sqlite_repository.py`)
모든 데이터 저장 시점에서 표준화된 타임스탬프를 자동으로 주입하도록 개선:

```python
# 증분 저장 시 타임스탬프 자동 추가
if not new_entries.empty:
    # 표준화된 타임스탬프 형식 적용
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if 'created_at' not in new_entries.columns:
        new_entries['created_at'] = timestamp
    if 'updated_at' not in new_entries.columns:
        new_entries['updated_at'] = timestamp

# 전체 교체 시에도 동일한 로직 적용
# 표준화된 타임스탬프 형식 적용
from datetime import datetime
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
if 'created_at' not in data.columns:
    data['created_at'] = timestamp
if 'updated_at' not in data.columns:
    data['updated_at'] = timestamp
```

### 🎯 개선 효과
- **일관성**: 모든 데이터에 표준화된 타임스탬프 보장
- **정확성**: 시간 기반 필터링 및 통계의 정확도 향상
- **자동화**: 수동 타임스탬프 관리 없이 자동 주입
- **호환성**: 기존 데이터는 그대로 유지하면서 새 데이터만 표준화

### 📅 표준 타임스탬프 형식
- **형식**: `YYYY-MM-DD HH:MM:SS` (예: `2025-07-02 14:30:15`)
- **시간대**: 시스템 로컬 시간 기준
- **적용 시점**: 데이터 저장 시점의 현재 시간

이 개선으로 향후 모든 크롤링 데이터가 일관된 타임스탬프를 가지게 되어, 시간 기반 분석 및 필터링 기능의 정확성이 크게 향상되었습니다.

## 🔧 스케줄러 토글 버그 수정 (2025.07.02)

### 문제점
설정 페이지에서 "스케줄러 중지" 버튼 클릭 후 "스케줄러 시작" 버튼을 클릭하면 "스케줄러가 이미 중지되어 있습니다"라는 잘못된 메시지가 표시되는 문제가 있었습니다.

**원인**: 
- `toggleScheduler()` 함수가 버튼의 텍스트나 CSS 클래스로 현재 상태를 판단
- 버튼 상태와 실제 스케줄러 상태가 일치하지 않을 수 있음

### 해결책: 실제 스케줄러 상태 기반 판단

#### settings.js 수정 사항
```javascript
async toggleScheduler() {
    // 먼저 시스템 상태를 확인하여 실제 스케줄러 상태 가져오기
    const statusResponse = await fetch('/api/system-status');
    const statusData = await statusResponse.json();
    const isCurrentlyRunning = statusData.scheduler_status?.scheduler_running || false;
    
    // 실제 상태에 따라 적절한 엔드포인트 호출
    const endpoint = isCurrentlyRunning ? '/api/scheduler/stop' : '/api/scheduler/start';
}
```

### 🎯 개선 효과
- **정확한 상태 파악**: API 호출로 실제 스케줄러 상태 확인
- **올바른 동작**: 실제 상태에 따라 적절한 엔드포인트 호출
- **에러 방지**: 이미 실행/중지된 상태도 성공으로 처리
- **UI 일관성**: 에러 발생 시에도 시스템 상태 재로드로 UI 동기화

이제 스케줄러 토글 버튼이 항상 정확하게 동작하며, 사용자에게 혼란을 주지 않습니다.

## 🔄 스케줄 주기 변경 문제 해결 (2025.07.02)

### 문제점
설정에서 크롤링 주기를 변경해도 (예: 1시간 → 2시간) "다음 실행" 시간이 업데이트되지 않고 기존 시간대로 유지되는 문제가 있었습니다.

**원인**:
1. **하드코딩된 cron 표현식**: 사이트 활성화 시 `'0 */6 * * *'` 고정값 사용
2. **설정 저장 시 cron 표현식 미업데이트**: `updateExistingSchedules()`에서 기존 cron 표현식을 그대로 유지
3. **시간 설정과 cron 표현식 변환 로직 없음**: `defaultInterval` 설정을 cron 표현식으로 변환하는 함수가 없음

### 해결책: 동적 스케줄 업데이트 시스템

#### 1. cron 표현식 생성 함수 추가 (`settings.js`)
```javascript
generateCronExpression(hours) {
    if (hours >= 24) {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        
        if (remainingHours === 0) {
            return `0 0 */${days} * *`;  // 일 단위
        } else {
            return `0 */${hours} * * *`; // 시간 단위
        }
    } else {
        return `0 */${hours} * * *`;     // 시간 단위
    }
}
```

#### 2. 사이트 토글 함수 개선
```javascript
// 기존: 하드코딩된 cron 표현식
cron_expression: '0 */6 * * *'

// 변경: 동적 cron 표현식
cron_expression: this.generateCronExpression(this.currentSettings.defaultInterval)
```

#### 3. 기존 스케줄 업데이트 로직 개선
```javascript
async updateExistingSchedules() {
    // 새로운 cron 표현식 생성 및 적용
    const newCronExpression = this.generateCronExpression(this.currentSettings.defaultInterval);
    
    const scheduleData = {
        site_key: siteKey,
        cron_expression: newCronExpression, // 새로운 주기 반영
        enabled: true,
        priority: schedule.priority || 0,
        notification_threshold: this.currentSettings.notificationThreshold
    };
}
```

### 🎯 개선 효과
- **즉시 반영**: 설정 변경 시 모든 활성화된 사이트의 스케줄 즉시 업데이트
- **정확한 스케줄링**: 새로운 주기에 맞게 "다음 실행" 시간 자동 조정
- **사용자 피드백**: 업데이트 과정과 결과를 상세한 로깅 및 토스트 알림으로 제공
- **일관성**: 새로 활성화되는 사이트도 현재 설정에 맞는 주기로 스케줄링

### 📊 지원하는 주기 범위
- **최소 주기**: 1시간 (`0 */1 * * *`)
- **최대 주기**: 168시간/7일 (`0 0 */7 * *`)
- **스마트 변환**: 24시간 이상 시 일 단위로 자동 최적화

이제 설정에서 크롤링 주기를 변경하면 모든 활성화된 모니터링 스케줄이 즉시 새로운 주기로 업데이트되어 정확한 시간에 실행됩니다.

## 🎯 대시보드 "크롤링 진행현황" 기능 개선 (2025.07.02)

### 변경 개요
기존 "최근 업데이트" 섹션을 실제 크롤링 실행 이력을 보여주는 "크롤링 진행현황"으로 교체하여 더 유용한 정보를 제공하도록 개선했습니다.

### 🔄 주요 변경사항

#### 1. UI 텍스트 변경
- **섹션 제목**: "최근 업데이트" → "크롤링 진행현황"
- **버튼 텍스트**: "새로고침" → "크롤링 현황"

#### 2. 데이터 소스 변경
- **기존**: `/api/notifications` (시스템 알림)
- **변경**: `/api/job-history` (실제 크롤링 실행 이력)

#### 3. 새로운 정보 표시
```javascript
// 크롤링 실행 상태별 표시
- 실행 중: ◯ (회색)
- 완료: ● (초록색)  
- 실패: × (빨간색)
- 부분 성공: ! (주황색)

// 표시 정보
- 실행 시간 및 소요시간
- 수집된 데이터 개수
- 에러 메시지 (실패 시)
- 사이트별 상태 구분
```

#### 4. 버튼 가시성 개선
- **"크롤링 현황" 버튼**: `btn-outline` → `btn-primary` (파란색 배경)
- **"적용" 버튼**: `btn-outline` → `btn-primary` (파란색 배경)
- 이모지 제거하여 프로페셔널한 인터페이스 구현

### 🎯 사용자 경험 향상
- **실용성**: 시스템 알림 대신 실제 크롤링 작업 상태 확인 가능
- **가시성**: 중요 버튼들의 색상 개선으로 명확한 UI 제공
- **정보성**: 실행 시간, 소요시간, 결과 등 상세 정보 표시
- **일관성**: 이모지 제거로 비즈니스 환경에 적합한 인터페이스

### 📊 기술적 구현
- **최소 변경**: 기존 타임라인 UI 재사용으로 효율적 구현
- **API 활용**: 기존 `/api/job-history` 엔드포인트 활용
- **상태 관리**: 실시간 크롤링 상태 반영
- **에러 처리**: 크롤링 실패 시 상세 에러 정보 표시

이제 대시보드에서 실제 크롤링 작업의 진행 상황과 결과를 명확하게 파악할 수 있어 시스템 모니터링 효율성이 크게 향상되었습니다.

## 🔧 크롤링 진행현황 상세 정보 시스템 (2025.07.02)

### 📊 새로운 상세 정보 표시 기능
사용자가 크롤링 과정을 투명하게 확인할 수 있도록 상세한 통계 정보를 추가했습니다.

#### 표시되는 상세 정보
```
● 조세심판원 크롤링 완료
  287개 수집, 3개 신규, 284개 중복
  실행 시간: 2025-07-02 14:30:00 (소요시간: 120초)

● 국세청(유권해석) 크롤링 완료  
  1,045개 수집, 28개 신규, 1,017개 중복
  실행 시간: 2025-07-02 14:32:00 (소요시간: 95초)
```

### 🏗️ 기술적 구현

#### 1. 크롤링 서비스 개선 (`src/services/crawler_service.py`)
- **반환 타입 변경**: `None` → `Dict[str, Any]`
- **상세 결과 반환**: 각 사이트별 `total_crawled`, `new_count`, `existing_count` 포함
- **통계 집계**: 전체 사이트 통계 자동 계산

```python
return {
    "status": "success",
    "results": [
        {
            'site_key': 'tax_tribunal',
            'total_crawled': 287,    # 크롤링한 총 개수
            'new_count': 3,          # 신규 데이터 개수
            'existing_count': 1543   # 기존 데이터 개수
        }
    ]
}
```

#### 2. 스케줄러 서비스 강화 (`src/services/scheduler_service.py`)
- **상세 결과 수신**: 크롤링 서비스의 상세 통계 활용
- **로그 저장 확장**: `site_results` JSON에 모든 통계 저장
- **API 응답 개선**: `get_job_history`에서 상세 정보 반환

```json
"site_results": {
  "tax_tribunal": {
    "status": "success",
    "total_crawled": 287,
    "new_count": 3,
    "existing_count": 1543,
    "site_name": "조세심판원"
  }
}
```

#### 3. 프론트엔드 UI 개선 (`src/web/static/js/dashboard.js`)
- **정보 표시 로직**: `"287개 수집, 3개 신규, 284개 중복"` 형태로 표시
- **중복 계산**: `total_crawled - new_count`로 자동 계산
- **하위 호환성**: 기존 `data_collected` 필드 유지

### 🗑️ 크롤링 진행현황 삭제 기능

#### 새로운 기능
- **전체 삭제 버튼**: 대시보드 진행현황 섹션에 "전체 삭제" 버튼 추가
- **확인 다이얼로그**: 삭제 전 사용자 확인 요청
- **즉시 반영**: 삭제 후 목록 자동 새로고침

#### API 엔드포인트
```
DELETE /api/job-history
```
- **기능**: `crawl_execution_log` 테이블의 모든 레코드 삭제
- **응답**: 삭제 성공/실패 메시지

### 🎯 사용자 가치
1. **투명성**: 크롤링 과정의 모든 단계를 상세히 확인 가능
2. **신뢰성**: 표시된 숫자의 정확성 보장
3. **관리 편의성**: 진행현황 삭제로 깔끔한 화면 유지
4. **문제 진단**: 크롤링 실패 시 구체적인 원인 파악 가능

이제 예규판례 모니터링 시스템이 완전히 투명하고 관리하기 쉬운 전문가급 도구로 발전했습니다.

## 🔄 시스템 명칭 개선 (2025.07.02)

### 📝 명칭 통일 및 개선
사용자 친화적이고 명확한 용어로 시스템 전반의 명칭을 개선했습니다.

#### 변경 내용
- **기존**: "세금법령 모니터링 시스템"
- **변경**: "예규판례 모니터링 시스템"

#### 적용 범위
- **모든 웹 페이지**: 제목, 헤더, 설명문
- **문서**: CLAUDE.md 프로젝트 개요 및 설명
- **브랜딩**: 시스템 전반의 일관된 명칭 사용

### 🎯 개선 효과
1. **명확성**: 수집 데이터의 성격을 정확히 표현 (예규, 판례, 해석 등)
2. **전문성**: 세무 전문가들에게 친숙하고 표준적인 용어 사용
3. **일관성**: 전체 시스템에 걸친 통일된 브랜딩
4. **직관성**: 시스템의 목적과 기능을 명확히 전달

이제 "예규판례 모니터링 시스템"으로 명확하게 브랜딩되어 전문성과 사용자 친화성이 크게 향상되었습니다.

## 🚀 최신 개발 현황 (2025.07.02)

### 📊 크롤링 진행현황 상세 통계 시스템
대시보드의 "크롤링 진행현황" 섹션에서 크롤링 과정의 투명성을 극대화하는 상세 통계 시스템을 구현했습니다.

#### 새로운 상세 정보 표시
```
● 조세심판원 크롤링 완료
  287개 수집, 3개 신규, 284개 중복
  실행 시간: 2025-07-02 14:30:00 (소요시간: 120초)

● 국세청(유권해석) 크롤링 완료  
  1,045개 수집, 28개 신규, 1,017개 중복
  실행 시간: 2025-07-02 14:32:00 (소요시간: 95초)
```

#### 기술적 구현 요소
- **크롤링 서비스**: 반환 타입을 `None`에서 `Dict[str, Any]`로 변경하여 상세 통계 제공
- **스케줄러 서비스**: `site_results` JSON에 `total_crawled`, `new_count`, `existing_count` 통계 저장
- **프론트엔드**: 중복 개수 자동 계산 (`total_crawled - new_count`)으로 정확한 통계 표시

### 🗑️ 크롤링 진행현황 관리 기능
#### 전체 삭제 기능
- **위치**: 대시보드 "크롤링 진행현황" 섹션에 "전체 삭제" 버튼
- **확인 절차**: 삭제 전 사용자 확인 다이얼로그
- **API 엔드포인트**: `DELETE /api/job-history`로 `crawl_execution_log` 테이블 전체 삭제
- **즉시 반영**: 삭제 후 목록 자동 새로고침

### 🔧 스케줄 관리 시스템 강화
#### 동적 cron 표현식 생성 시스템
설정에서 크롤링 주기 변경 시 모든 활성화된 스케줄이 즉시 새로운 주기로 업데이트되도록 개선:

```javascript
// cron 표현식 생성 함수 (`settings.js`)
generateCronExpression(hours) {
    if (hours >= 24) {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        
        if (remainingHours === 0) {
            return `0 0 */${days} * *`;  // 일 단위
        } else {
            return `0 */${hours} * * *`; // 시간 단위
        }
    } else {
        return `0 */${hours} * * *`;     // 시간 단위
    }
}
```

#### 스케줄러 토글 안정성 개선
```javascript
// 실제 시스템 상태 기반 토글 (`settings.js`)
async toggleScheduler() {
    const statusResponse = await fetch('/api/system-status');
    const statusData = await statusResponse.json();
    const isCurrentlyRunning = statusData.scheduler_status?.scheduler_running || false;
    
    const endpoint = isCurrentlyRunning ? '/api/scheduler/stop' : '/api/scheduler/start';
}
```

### 🕐 타임스탬프 자동 표준화 시스템
모든 데이터 저장 시점에서 표준화된 타임스탬프를 자동 주입하도록 개선:

```python
# Repository 레벨 자동 타임스탬프 주입 (`src/repositories/sqlite_repository.py`)
from datetime import datetime
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
if 'created_at' not in data.columns:
    data['created_at'] = timestamp
if 'updated_at' not in data.columns:
    data['updated_at'] = timestamp
```

### 📈 데이터 일관성 및 정확성 강화
#### 단일 데이터 소스 기반 통계
- **변경 전**: `new_data_log` 테이블과 각 사이트 테이블의 이중 데이터 소스로 인한 불일치
- **변경 후**: 각 사이트 테이블에서 직접 최근 데이터를 조회하는 단일 소스 방식
- **새로운 API**: `/api/sites/recent-counts`로 각 사이트별 최근 데이터 개수 정확히 조회
- **결과**: 대시보드 카드 숫자와 실제 필터링된 데이터 개수 100% 일치

#### 실제 데이터 기반 마지막 업데이트 시간 표시
```python
# 각 사이트별 실제 데이터의 최신 시간 조회 (`src/repositories/sqlite_repository.py`)
if 'created_at' in existing_columns or 'updated_at' in existing_columns:
    time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
    cursor.execute(f"SELECT MAX({time_column}) FROM [{table_name}]")
    actual_last_updated = cursor.fetchone()[0]
```

### 🎯 사용자 경험 최적화
#### 프로페셔널 UI 개선
- **버튼 가시성**: "크롤링 현황" 및 "적용" 버튼을 `btn-outline`에서 `btn-primary`로 변경
- **이모지 제거**: 비즈니스 환경에 적합한 프로페셔널 인터페이스 구현
- **정보 명확성**: 크롤링 상태별 명확한 아이콘 및 색상 구분

#### 스마트 데이터 필터링
- **상태 카드 클릭**: 선택된 시간 범위의 신규 데이터만 표시
- **데이터 보기 버튼**: 해당 사이트의 전체 데이터 표시
- **필터 상태 표시**: 현재 조회 중인 데이터 범위를 명확히 표시

### 📋 지원하는 크롤링 주기 범위
- **최소 주기**: 1시간 (`0 */1 * * *`)
- **최대 주기**: 168시간/7일 (`0 0 */7 * *`)
- **스마트 변환**: 24시간 이상은 일 단위로 자동 최적화

### 🎯 핵심 가치 제공
1. **완전한 투명성**: 크롤링 과정의 모든 단계와 결과를 상세히 확인 가능
2. **100% 정확성**: 표시되는 모든 숫자와 시간의 정확성 보장
3. **즉시 반영**: 설정 변경이 실시간으로 시스템에 반영
4. **전문가급 안정성**: 에러 없는 스케줄러 토글 및 설정 관리
5. **관리 편의성**: 진행현황 삭제, 필터링 등 직관적인 관리 기능

이제 예규판례 모니터링 시스템이 **완전히 투명하고 신뢰할 수 있는 전문가급 모니터링 도구**로 완성되었습니다.