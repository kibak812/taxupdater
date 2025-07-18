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
# 로컬: http://localhost:8001
# 외부: https://taxupdater-monitor.loca.lt (고정 URL)
```

### 자동 배포 설정 (LocalTunnel)
```bash
# LocalTunnel 자동 설정 (한 번만 실행)
./setup_localtunnel.sh

# 서비스 관리
systemctl --user status taxupdater localtunnel    # 상태 확인
systemctl --user restart taxupdater localtunnel   # 재시작
systemctl --user stop taxupdater localtunnel      # 중지

# 고정 접속 URL (재부팅 후에도 동일)
https://taxupdater-monitor.loca.lt
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

기술적 상세사항은 [기술적 세부사항 문서](docs/TECHNICAL_DETAILS.md)를 참고하세요.

### 주요 포인트
- SQLite 제약사항 회피 방법
- WebSocket 진행률 업데이트 (.value 속성 사용)
- 사이트별 크롤링 특이사항 (행정안전부, 감사원 등)
- 데이터 무결성 및 누적 저장 시스템

## 현재 시스템 상태

현재 시스템의 상태와 개발 이력은 [변경 이력 문서](docs/CHANGELOG.md)를 참고하세요.

### 주요 성과
- 모든 크롤러 정상 작동
- 웹 인터페이스 완성
- 자동 모니터링 시스템 구축 완료
- LocalTunnel 기반 고정 URL 제공

## 개발 가이드라인
- 파일 수정 전 항상 Read 도구로 파일 내용 확인
- 500줄 초과 파일 발견 시 모듈화 검토  
- 커밋 메시지는 간결하게 작성
- 웹 전용 환경 (tkinter 의존성 완전 제거)
- 모든 데이터 접근 시 컬럼 존재 여부 확인
- UNIQUE constraint 에러 시 INSERT OR IGNORE 처리

## 참고 문서
- [기술적 세부사항](docs/TECHNICAL_DETAILS.md): SQLite, WebSocket, 크롤러별 특이사항 등
- [배포 가이드](docs/DEPLOYMENT.md): LocalTunnel, Fly.io, systemd 설정
- [문제 해결 가이드](docs/TROUBLESHOOTING.md): 일반적인 문제와 해결 방법
- [변경 이력](docs/CHANGELOG.md): 개발 히스토리와 업데이트 내역


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

## 접속 방법

### 로컬 접속
```
http://localhost:8001
```

### 외부 접속 (고정 URL)
```
https://taxupdater-monitor.loca.lt
```

이 URL을 브라우저 북마크에 저장하여 영구적으로 사용할 수 있습니다.

---

예규판례 모니터링 시스템이 **완전 자동화된 전문가급 모니터링 플랫폼**으로 완성되었습니다.

## 🔍 웹 데이터 테이블 필터링 시스템 (2025.07.14)

### 📋 필터링 기능 추가
기존 웹 데이터 테이블에 세목 및 유형별 필터링 기능을 추가하여 대용량 데이터를 효율적으로 탐색할 수 있도록 개선했습니다.

### 🎯 사이트별 필터링 지원
- **조세심판원**: 세목 + 유형 필터 (둘 다 지원)
- **국세청 유권해석**: 세목 필터만 지원
- **기타 사이트**: 필터 숨김 (기존 방식 유지)

### 🚀 스마트 필터링 시스템

#### **이중 모드 시스템**
- **일반 모드**: 서버 사이드 페이지네이션 (기본)
- **필터 모드**: 전체 데이터 로드 후 클라이언트 사이드 필터링

#### **사용자 친화적 페이지네이션**
- 필터 적용 시 자동으로 1페이지로 이동
- 필터링된 데이터만 페이지네이션에 표시
- 페이지 이동 시 필터 조건 유지

#### **동적 필터 옵션**
- 실제 데이터에서 필터 옵션 자동 생성
- 세목 및 유형 값을 알파벳순으로 정렬
- 필터 해제 시 자동으로 일반 모드로 복귀

### 🎨 UI/UX 개선사항

#### **필터 패널**
- 토글 버튼으로 필터 패널 열기/닫기
- 세목 및 유형 드롭다운 선택
- "모두 지우기" 버튼으로 필터 초기화

#### **상태 표시**
- 필터 조건이 제목에 명확히 표시
- 필터링된 항목 수 정확히 표시
- "전체 데이터 보기" 링크 제공

### 🔧 기술적 특징

#### **성능 최적화**
- 필터 미적용 시: 서버 부하 최소화 (50개씩 페이지 로드)
- 필터 적용 시: 한 번에 전체 데이터 로드 후 클라이언트 처리

#### **상태 관리**
- `isFiltered` 플래그로 모드 구분
- 필터 상태에 따른 데이터 로딩 방식 자동 전환
- 검색 기능과 필터 기능 병행 지원

### 📊 사용 워크플로우
1. **필터 버튼 클릭** → 필터 패널 열기
2. **세목/유형 선택** → 자동으로 전체 데이터 로드
3. **1페이지 표시** → 필터링된 결과를 처음부터 표시
4. **페이지 이동** → 필터 조건 유지하면서 탐색
5. **필터 해제** → 일반 페이지 모드로 복귀

### 💡 핵심 개선사항
- **전체 데이터 기준 필터링**: 더 이상 각 페이지별로 필터링하지 않음
- **즉시 1페이지 이동**: 필터 적용 시 자동으로 첫 페이지로 이동
- **연속적인 데이터 보기**: 필터링된 데이터를 연속적으로 확인 가능
- **직관적인 상태 표시**: 현재 필터 조건과 결과 수를 명확히 표시

이제 세무 전문가들이 조세심판원과 국세청 유권해석 데이터를 세목 및 유형별로 효율적으로 필터링하여 원하는 정보를 빠르게 찾을 수 있습니다.

## 🏷️ 웹 데이터 테이블 세목 컬럼 추가 (2025.07.14)

### 📋 개선사항
기존 웹 데이터 테이블에서 세목 정보가 표시되지 않던 문제를 해결하여, 세목 정보를 체계적으로 수집하고 있는 사이트들에서 웹 인터페이스를 통해 세목 정보를 확인할 수 있도록 개선했습니다.

### 🛠️ 구현 내용

#### 1. 세목 정보 수집 현황 확인
- **국세청 유권해석**: 17개 세목 카테고리 (양도소득세, 법인세, 조세특례 등)
- **행정안전부**: 6개 세목 카테고리 (취득세, 재산세, 지방소득세 등)
- **조세심판원**: 기존부터 세목 정보 표시 중

#### 2. 웹 테이블 컬럼 추가
- **국세청 유권해석** (`nts_authority`): 세목 컬럼 추가
- **행정안전부** (`mois`): 세목 컬럼 추가
- **테이블 구조**: 기관 → 세목 → 문서번호 → 제목 → 게시일 → 수집일

#### 3. 기술적 구현
- **파일 수정**: `src/web/static/js/data_table.js`
- **헤더 추가**: `updateTableHeader()` 함수에서 사이트별 세목 컬럼 정의
- **데이터 표시**: `createTableRow()` 함수에서 세목 정보 표시 로직 추가
- **정렬 기능**: 세목 컬럼에 대한 정렬 기능 지원

### 📊 세목 정보 표시 현황
```
조세심판원: 세목 + 유형 + 청구번호 + 제목 + 결정일 + 수집일
국세청 유권해석: 세목 + 문서번호 + 제목 + 생산일자 + 수집일  
행정안전부: 세목 + 문서번호 + 제목 + 생산일자 + 수집일
국세청 판례: 문서번호 + 제목 + 생산일자 + 수집일 (세목 정보 없음)
기타 사이트: 기존 컬럼 구조 유지
```

### 💡 사용자 경험 개선
- **세목별 분류**: 각 기관의 세목 카테고리를 통해 데이터 분류 가능
- **검색 향상**: 세목 정보도 검색 대상에 포함되어 더 정확한 검색 가능
- **정렬 기능**: 세목별 정렬을 통해 관련 데이터 그룹화 가능
- **일관성**: 세목 정보가 있는 사이트는 모두 동일한 방식으로 표시

### 🔧 코드 변경 요약
- 사이트별 조건부 테이블 헤더 생성
- 세목 정보 추출 및 표시 로직 추가
- 정렬 기능에 세목 컬럼 포함
- 반응형 디자인 유지

이 개선으로 웹 인터페이스에서 세목 정보를 체계적으로 확인할 수 있게 되어, 세무 전문가들이 더 효율적으로 데이터를 분석할 수 있습니다.

## 🔗 국세청 링크 생성 시스템 개선 (2025.07.13)

### 📋 문제 해결
기존 복잡한 `ntstDcmId` 추출 방식의 한계를 극복하고, 문서번호 기반 검색 링크 생성 방식으로 전환하여 **링크 생성 성공률을 0%에서 100%로 개선**했습니다.

### 🛠️ 주요 변경사항

#### 1. 새로운 링크 생성 시스템
- **링크 유틸리티**: `src/utils/link_generator.py` 신규 생성
- **생성 방식**: 문서번호 → URL 인코딩 → 검색 링크 자동 생성
- **링크 형태**: `https://taxlaw.nts.go.kr/is/USEISA001M.do?schVcb={문서번호}&searchType=totalSearch`

#### 2. 크롤러 로직 간소화
- **nts_authority_crawler.py**: 복잡한 JavaScript 로직 제거 (60줄 → 15줄)
- **nts_precedent_crawler.py**: ntstDcmId 추출 로직 제거 및 간소화
- **개선 효과**: 코드 가독성 향상, 유지보수성 개선, 사이트 구조 변경에 독립적

#### 3. 기존 데이터 완전 복구
- **처리 규모**: 10,155건 (유권해석 5,052건 + 판례 5,103건)
- **성공률**: 100% (모든 데이터에 유효한 링크 생성)
- **배치 처리**: 안전하고 효율적인 대량 업데이트

### 📊 성과 요약
```
링크 생성 성공률: 0% → 100%
코드 복잡도: 대폭 감소 (JavaScript 로직 제거)
유지보수성: 향상 (사이트 구조 독립적)
사용자 경험: 개선 (모든 문서에 직접 접근 링크 제공)
```

### 🔧 기술적 개선점
- **모듈화**: 재사용 가능한 링크 생성 유틸리티
- **안정성**: URL 인코딩 및 유효성 검증 기능
- **확장성**: 향후 다른 사이트에도 적용 가능한 구조
- **실용성**: 검색결과창으로 직접 이동하여 즉시 문서 확인

## 🔧 링크 생성 시스템 최종 개선 (2025.07.14)

### 📋 문제 해결
자동 크롤링에서 국세청 데이터의 링크가 생성되지 않는 문제를 근본적으로 해결했습니다.

### 🛠️ 개선 내용
- **이전 방식**: 크롤링 → 새 데이터 탐지 → 링크 생성 → 저장 (복잡하고 오류 발생 가능)
- **새로운 방식**: 크롤링 시점에 즉시 링크 생성 (심플하고 안정적)

### 📊 코드 변경
```python
# 크롤링 시점에 바로 링크 생성
data.append({
    "세목": item.get('taxLabel', ''),
    "생산일자": item.get('productionDate', ''),
    "문서번호": doc_number,
    "제목": item.get('title', ''),
    "링크": generate_nts_search_link(doc_number, "authority") or ''
})
```

### ✅ 개선 효과
- **코드 간소화**: 복잡한 후처리 로직 제거
- **안정성 향상**: 링크 생성 실패 가능성 제거  
- **유지보수성**: 더 이해하기 쉬운 코드 구조
- **성능**: `generate_nts_search_link`가 가벼워서 성능 영향 없음

### 📈 최종 결과
```
링크 생성률: 100% (모든 새로운 데이터에 링크 포함)
코드 복잡도: 대폭 감소 (후처리 로직 제거)
유지보수성: 향상 (심플한 구조)
시스템 안정성: 완전 안정화
```

## 🎨 브라우저 알림 기능 설정 페이지 통합 (2025.07.14)

### 📋 문제 해결
기존 대시보드에서 "설정" 버튼 클릭 시 팝업 모달로만 표시되던 브라우저 알림 설정을 기존 `/settings` 페이지의 "알림 설정" 섹션과 조화롭게 통합하여 일관된 UX 제공

### 🛠️ 주요 변경사항

#### 1. 대시보드 설정 버튼 동작 변경
- **이전**: 팝업 모달 표시 (`showSettingsModal()`)
- **변경**: 설정 페이지로 이동 (`window.location.href = '/settings'`)

#### 2. 설정 페이지 "알림 설정" 섹션 확장
- **브라우저 푸시 알림 카드 추가**: 토글 스위치 및 권한 상태 표시
- **권한 관리 인터페이스**: 권한 상태 실시간 표시 및 요청 버튼
- **WebSocket 실시간 알림**: 기존 기능과 조화로운 배치

#### 3. JavaScript 기능 이전 및 통합
- `dashboard.js`의 브라우저 알림 관련 메서드들을 `settings.js`로 이전
- 설정 페이지에서 직접 브라우저 알림 권한 관리
- LocalStorage 기반 설정 저장/로드 기능 통합

#### 4. 코드 정리 및 최적화
- 더 이상 사용하지 않는 설정 모달 HTML 및 관련 JavaScript 제거
- 모달 관련 이벤트 리스너 및 메서드 정리
- 코드 중복 제거 및 구조 단순화

### 🎯 새로운 사용자 워크플로우
1. **대시보드 → 설정**: "설정" 버튼 클릭으로 전용 설정 페이지 이동
2. **통합 알림 설정**: 브라우저 알림과 WebSocket 알림을 한 곳에서 관리
3. **실시간 권한 관리**: 권한 상태 확인 및 즉시 요청 가능
4. **일관된 설정 경험**: 모든 시스템 설정이 한 페이지에서 통합 관리

### ✅ 개선 효과
- **UX 일관성**: 팝업 대신 전용 페이지로 일관된 네비게이션
- **기능 통합**: 브라우저 알림이 기존 알림 설정과 조화롭게 통합
- **코드 효율성**: 모달 관련 불필요한 코드 제거로 유지보수성 향상
- **설정 중앙화**: 모든 알림 관련 설정을 한 곳에서 관리

### 🔧 기술적 구현 세부사항
```javascript
// settings.js에 추가된 브라우저 알림 기능
- initBrowserNotifications(): 브라우저 알림 초기화
- requestNotificationPermission(): 권한 요청 처리
- toggleBrowserNotifications(): 알림 활성화/비활성화
- updateNotificationUI(): UI 상태 업데이트
- loadNotificationSetting/saveNotificationSetting(): 설정 영속성
```

### 📊 UI 개선사항
- **브라우저 푸시 알림 카드**: 토글 스위치와 설명 텍스트
- **권한 상태 표시**: 허용됨/거부됨/미설정 상태를 색상으로 구분
- **권한 요청 버튼**: 필요시에만 표시되는 동적 인터페이스
- **반응형 디자인**: 모바일 환경에서도 최적화된 레이아웃

이제 예규판례 모니터링 시스템의 설정 관리가 더욱 직관적이고 통합된 경험을 제공합니다.
