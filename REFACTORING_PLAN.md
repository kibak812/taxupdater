### **TaxUpdater 시스템 점진적 개선 계획 (Low-Risk, High-Return)**

**1. 목표:** 현재의 안정적인 아키텍처와 코드를 최대한 존중하고 유지하면서, 타입 안전성과 로깅 체계를 보강하여 향후 유지보수의 편의성을 향상시킵니다. **대규모 리팩토링이 아닌, 안전한 기능 추가 및 개선**에 초점을 맞춥니다.

**2. 핵심 전략:**
*   **호환성 유지:** 기존의 핵심 데이터 형식인 `pandas.DataFrame`을 그대로 사용합니다. 시스템의 서비스, 저장소, 웹 로직은 **수정하지 않습니다.**
*   **점진적 개선:** 크롤러의 결과 값에만 `TaxData` 모델을 도입하여 타입 안정성을 확보하고, 중앙 로깅 시스템을 도입하여 `print()`문을 대체합니다.
*   **최소 리스크:** 이미 잘 작동하는 인터페이스, 의존성 주입, 서비스 로직은 그대로 유지합니다.

---

### **Phase 1: 로깅 시스템 도입 및 데이터 모델 정의 (안전한 기반 마련)**

이 단계는 시스템의 동작에 영향을 주지 않는 안전한 개선 작업입니다.

**Task 1-1: 중앙 로깅 시스템 도입**
*   **대상:** `print()`를 사용하는 모든 코드
*   **내용:** 애플리케이션의 진입점(`main.py`, `start_web.py`)에서 로깅 설정을 초기화하는 함수를 호출합니다. 이를 통해 모든 로그를 표준화된 형식으로 콘솔과 파일에 기록할 수 있습니다.
*   **실행 방안:**
    1.  `src/config/settings.py` 또는 별도의 유틸리티 파일에 `setup_logging` 함수를 추가합니다.
    2.  `main.py`와 `start_web.py` 최상단에서 `setup_logging()`을 호출합니다.
    3.  기존 `print()` 구문을 `logger.info()`, `logger.error()` 등으로 점진적으로 전환합니다. 특히 `try-except` 블록과 주요 실행 흐름을 로깅하는 것이 중요합니다.

**Task 1-2: `TaxData` 모델 정의 (크롤러 경계용)**
*   **파일:** `src/models.py` (신규 생성)
*   **내용:** 크롤러의 반환 값 타입을 명시하기 위한 `TaxData` 클래스를 정의합니다. **이 모델은 오직 크롤러의 출력 타입 힌팅용으로만 사용되며, 시스템의 다른 부분으로 전파되지 않습니다.**
*   **코드:**
    ```python
    # src/models.py
    from dataclasses import dataclass
    from datetime import date

    @dataclass
    class TaxData:
        case_number: str
        title: str
        publish_date: date
        source: str
        source_url: str
        content: str
        # 해시 생성 로직은 기존 서비스 레이어의 로직을 그대로 활용하므로 모델에서 제외
    ```

---

### **Phase 2: 크롤러-서비스 경계 리팩토링 (통제된 변경)**

**Task 2-1: 크롤러의 반환 타입을 `list[TaxData]`로 표준화**
*   **대상:** `CrawlerInterface` 및 모든 개별 크롤러 클래스
*   **내용:**
    1.  `CrawlerInterface`의 `crawl()` 메소드가 `list[TaxData]`를 반환하도록 시그니처를 수정합니다.
    2.  각 크롤러(`NTSCrawler` 등)는 HTML을 파싱하여 `pd.DataFrame` 대신 `TaxData` 객체의 리스트를 생성하여 반환하도록 내부 로직을 수정합니다.
*   **기대 효과:** 크롤러의 책임(HTML 파싱하여 구조화된 데이터 생성)이 더 명확해지고, 타입 힌팅으로 개발 편의성이 향상됩니다.

**Task 2-2: `CrawlingService`에 데이터 변환 로직 추가**
*   **대상:** `CrawlingService` (또는 크롤러를 호출하는 서비스)
*   **내용:** 크롤러로부터 `list[TaxData]`를 받은 직후, 이를 즉시 `pd.DataFrame`으로 변환하는 로직을 추가합니다. **이 변환 이후의 모든 서비스 로직(신규 데이터 비교, 저장소 호출 등)은 기존 코드를 그대로 재사용합니다.**
*   **코드 예시:**
    ```python
    # src/services/crawler_service.py (또는 유사 위치)

    import pandas as pd
    from typing import List
    from src.models import TaxData
    from dataclasses import asdict

    class CrawlingService:
        # ... 기존 __init__ ...

        def _convert_to_dataframe(self, data: List[TaxData]) -> pd.DataFrame:
            """TaxData 리스트를 DataFrame으로 변환하는 헬퍼 메소드"""
            if not data:
                return pd.DataFrame()
            return pd.DataFrame([asdict(d) for d in data])

        def execute_crawling(self): # 예시 메소드명
            # ...
            for crawler in self.crawlers:
                # 1. 크롤러는 TaxData 리스트를 반환
                crawled_data_list = crawler.crawl()

                # 2. 서비스는 즉시 DataFrame으로 변환
                crawled_df = self._convert_to_dataframe(crawled_data_list)

                # 3. 이후 모든 로직은 기존과 동일하게 DataFrame으로 처리
                if not crawled_df.empty:
                    new_entries_df = self.compare_and_get_new_entries(crawled_df)
                    self.repository.save(new_entries_df)
                    # ... 웹소켓 전송 등 ...
    ```

---

### **결론 및 기대 효과**

*   **안전성:** 이 계획은 현재 완벽하게 작동하는 **서비스, 저장소, 웹 인터페이스, 데이터베이스 스키마를 전혀 변경하지 않습니다.**
*   **최소 비용:** 수정이 필요한 부분은 각 크롤러의 반환 로직과, 이를 호출하는 서비스의 앞단에 위치한 변환 로직 뿐입니다.
*   **점진적 개선:** 위험 부담 없이 크롤러 코드의 명확성과 타입 안정성을 높이고, 중앙화된 로깅을 통해 시스템의 관측 가능성을 향상시킬 수 있습니다.