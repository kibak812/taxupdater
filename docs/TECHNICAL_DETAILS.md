# 기술적 세부사항

이 문서는 예규판례 모니터링 시스템의 상세한 기술적 구현 내용을 다룹니다.

## 목차
- [크롤러별 특이사항](#크롤러별-특이사항)
- [데이터베이스 관련](#데이터베이스-관련)
- [WebSocket 구현](#websocket-구현)
- [API 설계](#api-설계)
- [크롤링 설정](#크롤링-설정)

---

## 크롤러별 특이사항

### 행정안전부 크롤링 (2025.06.28)
행정안전부 사이트 접근 시 반드시 `upperMenuId` 파라미터가 필요합니다:

```python
# 올바른 URL (필수!)
mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000"

# 잘못된 URL (로그인 페이지로 리다이렉트됨)
mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000"
```

#### HTML 구조
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

### 감사원 크롤링 (2025.06.29)
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

#### 크롤링 범위
- **국세**: 5페이지
- **지방세**: 5페이지
- **총 10페이지**: 약 100개 항목 수집

### 크롤링 서비스 호출 방식
```python
# 개별 사이트: site_key → choice 변환 필요
site_to_choice_mapping = {
    "moef": "3", 
    "bai": "6",
    "tax_tribunal": "1",
    "nts_authority": "2",
    "nts_precedent": "5",
    "mois": "4"
}

# 누적 저장 방식 (기존 데이터 유지하면서 신규 데이터 추가)
save_data(site_key, new_entries, is_incremental=True)
```

## 데이터베이스 관련

### SQLite 제약사항 회피
기존 데이터가 있는 테이블에 `DEFAULT CURRENT_TIMESTAMP` 컬럼 추가 시:

```python
# 실패: ALTER TABLE ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# 성공: ALTER TABLE ADD COLUMN created_at TIMESTAMP + UPDATE 문 사용
```

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

### 타임스탬프 표준화 시스템
모든 데이터 저장 시점에서 표준화된 타임스탬프를 자동으로 주입:

```python
# Repository 레벨에서 자동 주입
from datetime import datetime
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
if 'created_at' not in data.columns:
    data['created_at'] = timestamp
if 'updated_at' not in data.columns:
    data['updated_at'] = timestamp
```

## WebSocket 구현

### 실시간 진행률 업데이트
```python
# WebSocketProgress 객체는 .value 속성 사용
progress.value = percentage  # O (올바른 방식)
progress['value'] = percentage  # X (tkinter 방식 - 사용하지 말 것)
```

### WebSocket 연결 상태 관리
```javascript
// window.app을 전역으로 노출하여 HTML에서 접근 가능
document.addEventListener('DOMContentLoaded', () => {
    app = new TaxCrawlerApp();
    window.app = app; // 전역으로 노출
});
```

## API 설계

### 주요 API 엔드포인트
```
# 크롤링 관련
POST   /api/crawl/{site_key}     - 개별 사이트 크롤링
POST   /api/crawl/all            - 전체 사이트 크롤링

# 데이터 조회
GET    /api/data/{site_key}      - 사이트별 데이터 조회
GET    /api/sites/recent-counts  - 각 사이트별 최근 데이터 개수

# 스케줄 관리
GET    /api/schedules            - 스케줄 목록 조회
POST   /api/schedules            - 스케줄 생성/수정
DELETE /api/schedules/{site_key} - 스케줄 삭제

# 시스템 상태
GET    /api/system-status        - 시스템 상태 조회
GET    /api/job-history          - 작업 이력 조회
DELETE /api/job-history          - 작업 이력 삭제

# 스케줄러 제어
POST   /api/scheduler/start      - 스케줄러 시작
POST   /api/scheduler/stop       - 스케줄러 중지
```

### FastAPI 경로 순서 중요사항
구체적인 경로를 와일드카드 경로보다 먼저 정의해야 합니다:

```python
@app.post("/api/crawl/all")        # 구체적 경로 먼저
async def start_all_crawling(): ...

@app.post("/api/crawl/{site_key}") # 와일드카드 경로 나중
async def start_crawling(): ...
```

## 크롤링 설정

### 기본 크롤링 설정
```python
CRAWLING_CONFIG = {
    "max_pages": 20,
    "max_items": 5000,
    "retry_count": 3,
    "timeout": 10
}
```

### 사이트별 설정 (src/config/settings.py)
```python
# 사이트별 URL 정의
URLS = {
    "tax_tribunal": "https://www.tt.go.kr/...",
    "nts_authority": "https://txsi.hometax.go.kr/...",
    # ...
}

# 데이터 컬럼 정의
DATA_COLUMNS = {
    "tax_tribunal": ["결정번호", "청구인", "처분청", ...],
    # ...
}

# 중복 제거용 키 컬럼
KEY_COLUMNS = {
    "tax_tribunal": "결정번호",
    "nts_authority": "문서번호",
    # ...
}
```

---

## 관련 문서
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)
- 문제 해결: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 배포 가이드: [DEPLOYMENT.md](./DEPLOYMENT.md)