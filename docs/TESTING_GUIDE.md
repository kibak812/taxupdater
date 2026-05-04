# 기능 유지 확인 가이드

현재 운영 경로는 FastAPI 웹 앱, SQLite 저장소, 스케줄러, 웹 알림, 사이트별 크롤러입니다. 과거 GUI/Excel 전환용 스크립트는 `archive/legacy/`에만 남아 있으므로 기본 회귀 검증에서는 사용하지 않습니다.

## 기본 테스트

```bash
# 단위/구조 회귀 테스트
./taxupdater_venv/bin/python -m unittest discover -s tests

# 문법 컴파일 체크
./taxupdater_venv/bin/python -m compileall -q src tests start_web.py

# whitespace/error marker 체크
git diff --check
```

현재 테스트는 다음 계층을 보호합니다.

- 웹 앱 팩토리와 라우트 등록 순서
- 대시보드/사이트 데이터 응답 payload 헬퍼
- WebSocket 연결 관리자 disconnect 동작
- SQLite 저장소의 저장, 로드, 신규 데이터 비교, 보조 컬럼 갱신, 최근 데이터 카운트
- CrawlingService의 숫자 키 최적화, 사이트 카탈로그 기반 키 컬럼, 신규 데이터 샘플/요약/태그 생성

## 로컬 웹 Smoke

운영 DB를 건드리지 않으려면 임시 DB 경로를 지정합니다.

```bash
DATABASE_PATH=/private/tmp/taxupdater_smoke.db \
./taxupdater_venv/bin/python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8011
```

다른 터미널에서 확인합니다.

```bash
curl -s -i http://127.0.0.1:8011/health
curl -s -i http://127.0.0.1:8011/api/dashboard
curl -s -i 'http://127.0.0.1:8011/api/sites/tax_tribunal/data?page=1&limit=2'
curl -s -i http://127.0.0.1:8011/api/stats
curl -s -i http://127.0.0.1:8011/api/schedules
curl -s -i http://127.0.0.1:8011/api/system-status
curl -s -i http://127.0.0.1:8011/static/js/dashboard.js
```

기대 결과:

- `/health`는 `200 OK`, `database: connected`
- 대시보드/통계/스케줄/시스템 상태 API는 `200 OK`
- `/dashboard`, `/settings`, `/data/tax_tribunal` 페이지가 렌더링되고 정적 CSS/JS가 `200 OK`
- 브라우저 콘솔에 새 에러가 없어야 함

## 크롤러 Smoke

전체 크롤링은 외부 사이트 부하와 실행 시간이 크므로, 기본 검증은 짧은 smoke로 제한합니다.

```bash
# Selenium/ChromeDriver 생성과 기본 페이지 로딩
./taxupdater_venv/bin/python -c "from src.crawlers.selenium_driver import create_chrome_driver; d=create_chrome_driver(); print(d.capabilities.get('browserVersion')); d.get('https://example.com'); print(d.title); d.quit()"

# requests 기반 대법원 선고예정 판결 1페이지 수집
./taxupdater_venv/bin/python -c "from src.crawlers.scourt_scheduled_decision_crawler import ScourtScheduledDecisionCrawler; c=ScourtScheduledDecisionCrawler(); df=c.crawl(max_pages=1); print(len(df)); print(list(df.columns)); print(c.last_checked_count)"
```

전체 크롤링 회귀는 배포 전이나 운영자가 명시적으로 승인한 때에만 실행합니다.

## 체크리스트

- [ ] 단위 테스트 전체 통과
- [ ] compileall 통과
- [ ] `git diff --check` 통과
- [ ] 임시 DB 기반 웹 서버 기동 성공
- [ ] 주요 API와 페이지가 `200 OK`
- [ ] 인앱 브라우저에서 대시보드 카드와 WebSocket 연결 표시 확인
- [ ] Selenium smoke 통과
- [ ] 최소 1개 실제 외부 크롤러 smoke 통과

## 문제 기록

테스트 중 문제를 발견하면 다음 정보를 남깁니다.

- 실패한 명령
- 에러 메시지 전문
- 실행 환경: OS, Python 버전, Chrome/ChromeDriver 버전
- 재현 단계와 사용한 `DATABASE_PATH`
