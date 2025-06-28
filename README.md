# Tax Law Updater

세금 관련 법령 및 해석 자료를 자동으로 수집하는 크롤링 시스템

## 기능

- 조세심판원 심판례 수집
- 국세법령정보시스템 유권해석 수집
- 국세법령정보시스템 판례 수집
- 기획재정부 해석 사례 수집
- 행정안전부 유권해석 수집
- 감사원 심사결정례 수집
- 주기적 자동 크롤링
- **웹 인터페이스 지원** (FastAPI 기반)

## 요구사항

- Python 3.7+
- Chrome/Chromium 브라우저
- ChromeDriver

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### CLI 실행
```bash
python example.py
```

### 웹 인터페이스 실행
```bash
python start_web.py
# 또는
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

## 최신 업데이트 (2025-06-28)

### 웹 환경 호환성 개선
- **웹 전용 레거시 크롤러 분리**: tkinter 의존성 없는 `web_legacy_crawlers.py` 추가
- **동적 크롤러 매핑**: 실제 사용 가능한 크롤러만 선택적으로 로드
- **비동기 크롤링 실행**: ThreadPoolExecutor를 통한 웹 환경에서의 안전한 크롤링
- **개선된 에러 처리**: 웹 인터페이스 크롤링 중 버튼 상태 관리 개선

### 주요 변경사항
1. **크롤러 서비스**: 사용 불가능한 크롤러 자동 제거 로직 추가
2. **웹 애플리케이션**: 레거시 크롤러의 조건부 로딩 및 웹 환경 최적화
3. **프론트엔드**: 크롤링 버튼 상태 관리 개선으로 UI 안정성 향상

## 프로젝트 구조

모듈화된 구조로 전환 완료:
- `src/crawlers/`: 크롤러 클래스들 (기본 + 웹용)
- `src/services/`: 비즈니스 로직 서비스
- `src/web/`: FastAPI 웹 애플리케이션
- `src/repositories/`: 데이터 저장소 (SQLite, Excel)
- `src/config/`: 설정 관리