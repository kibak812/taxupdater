"""
NTS 공통 기반 크롤러 (Template Method 패턴)

GPT-5.2 권장사항 반영:
- 95% 중복 코드를 추출하여 공통 기반 클래스로
- Template Method: crawl() 알고리즘 골격 정의
- Hook Methods: _generate_link()를 서브클래스에서 구현

훅 메서드 계약:
- _generate_link(doc_number): 문서번호로부터 링크 생성 (필수 구현)
"""

from abc import abstractmethod
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional, Callable, List, Dict, Any

from src.crawlers.base_crawler import BaseCrawler
from src.core.ports.crawler_port import ICrawler
from src.config.sites import get_site


class NTSBaseCrawler(BaseCrawler, ICrawler):
    """
    국세청 사이트 공통 크롤러 (Template Method)

    NTS Authority와 NTS Precedent 크롤러의 공통 로직을 추출.
    두 사이트는 동일한 DOM 구조와 "더보기" 버튼 패턴을 사용.

    서브클래스는 다음 메서드만 구현:
    - _generate_link(doc_number): 문서번호로 링크 URL 생성

    사용 예:
        class NTSAuthorityCrawler(NTSBaseCrawler):
            def __init__(self):
                super().__init__("국세청 유권해석", "nts_authority")

            def _generate_link(self, doc_number: str) -> str:
                return generate_nts_search_link(doc_number, "authority")
    """

    # CSS 선택자 상수 (두 사이트 공통)
    LIST_CONTAINER_SELECTOR = "#bdltCtl > li"
    MORE_BUTTON_CLASS = "more_show"

    # JavaScript 데이터 추출 스크립트 (공통)
    JS_EXTRACT_SCRIPT = """
    const items = document.querySelectorAll("#bdltCtl > li");

    const result = Array.from(items).map((item, index) => {
        try {
            const taxLabel = item.querySelector("ul.legislation_list li:nth-child(2)").getAttribute("title").trim();
            const productionDate = item.querySelector("ul.subs_detail li span.num").textContent.trim();
            const docNumber = item.querySelector("ul.subs_detail li strong").textContent.trim();
            const title = item.querySelector("a.subs_title strong").textContent.trim();

            return {taxLabel, productionDate, docNumber, title};
        } catch (e) {
            return {error: e.toString()};
        }
    });

    return result;
    """

    def __init__(self, site_name: str, site_key: str):
        """
        NTS 기반 크롤러 초기화

        Args:
            site_name: 사이트 표시명 (예: "국세청 유권해석")
            site_key: 사이트 키 (예: "nts_authority")
        """
        super().__init__(site_name, site_key)
        # Note: site_key는 BaseCrawler에서 이미 설정됨

        # SiteCatalog에서 URL 및 컬럼 정보 가져오기
        site_def = get_site(site_key)
        self.url = site_def.url
        self.data_columns = list(site_def.data_columns)
        self._key_column = site_def.key_column

    def get_key_column(self) -> str:
        """중복 제거용 키 컬럼 반환"""
        return self._key_column

    def get_site_key(self) -> str:
        """ICrawler 인터페이스 구현 - BaseCrawler와 일관성 유지"""
        return self.site_key

    # =========================================================================
    # Template Method: 알고리즘 골격
    # =========================================================================

    def crawl(
        self,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Template Method: NTS 사이트 크롤링 실행

        알고리즘 단계:
        1. 페이지 로드 및 초기화
        2. "더보기" 버튼으로 데이터 로딩 (_load_data)
        3. JavaScript로 데이터 추출 (_extract_data)
        4. 데이터 정리 및 링크 생성 (_clean_data)

        Args:
            progress_callback: 진행률 콜백 (0-100)
            status_callback: 상태 메시지 콜백
            **kwargs: max_items, max_load_attempts 등

        Returns:
            크롤링 결과 DataFrame
        """
        max_items = kwargs.get('max_items', self.config["max_items"])
        max_load_attempts = kwargs.get('max_load_attempts', self.config.get("max_load_attempts", 500))

        self.update_status_safely(status_callback, f"{self.site_name} 데이터 로딩 중...")

        driver = self.get_selenium_driver()

        try:
            # 타임아웃 설정
            driver.set_page_load_timeout(self.config.get("page_load_timeout", 60))
            driver.implicitly_wait(10)

            # 페이지 로드
            driver.get(self.url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, self.MORE_BUTTON_CLASS))
            )

            # Step 1: 데이터 로딩 (더보기 버튼 클릭)
            total_cases = self._load_data(driver, max_items, max_load_attempts, status_callback)

            # Step 2: 데이터 추출
            self.update_status_safely(
                status_callback,
                f"{self.site_name} 데이터 처리 중... (총 {total_cases}개 항목)"
            )
            raw_data = self._extract_data(driver, progress_callback)

            # Step 3: 데이터 정리 및 링크 생성
            cleaned_data = self._clean_data(raw_data)

            self.update_progress_safely(progress_callback, 100)
            self.update_status_safely(
                status_callback,
                f"{self.site_name} 크롤링 완료: 총 {len(cleaned_data)}개 사례 수집"
            )

            return cleaned_data

        except Exception as e:
            self.logger.error(f"{self.site_name} 크롤링 중 오류: {e}")
            return pd.DataFrame(columns=self.data_columns)
        finally:
            driver.quit()

    # =========================================================================
    # 공통 메서드 (두 크롤러에서 동일)
    # =========================================================================

    def _load_data(
        self,
        driver,
        max_items: int,
        max_load_attempts: int,
        status_callback: Optional[Callable[[str], None]]
    ) -> int:
        """
        더보기 버튼을 통해 데이터 로딩

        Args:
            driver: Selenium WebDriver
            max_items: 최대 로드 항목 수
            max_load_attempts: 최대 시도 횟수
            status_callback: 상태 메시지 콜백

        Returns:
            로드된 총 항목 수
        """
        total_cases = 0
        current_attempt = 0

        while total_cases < max_items and current_attempt < max_load_attempts:
            try:
                current_attempt += 1
                cases = driver.find_elements(By.CSS_SELECTOR, self.LIST_CONTAINER_SELECTOR)
                total_cases = len(cases)

                if total_cases >= max_items:
                    break

                # 더보기 버튼 클릭
                try:
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, self.MORE_BUTTON_CLASS))
                    )
                    driver.execute_script("arguments[0].click();", load_more_button)

                    # 5번마다 상태 업데이트 (성능 최적화)
                    if current_attempt % 5 == 0:
                        self.update_status_safely(
                            status_callback,
                            f"{self.site_name} 데이터 로딩 중: {total_cases}/{max_items} 사례"
                        )

                    time.sleep(1)  # 로딩 대기

                except Exception as e:
                    self.logger.debug(f"더 이상 항목을 로드할 수 없습니다: {e}")
                    break

            except Exception as e:
                self.logger.warning(f"데이터 로드 중 오류 발생: {e}")
                time.sleep(2)

        return total_cases

    def _extract_data(
        self,
        driver,
        progress_callback: Optional[Callable[[int], None]]
    ) -> List[Dict[str, Any]]:
        """
        JavaScript를 사용하여 DOM에서 데이터 추출

        Args:
            driver: Selenium WebDriver
            progress_callback: 진행률 콜백

        Returns:
            추출된 raw 데이터 리스트
        """
        raw_items = driver.execute_script(self.JS_EXTRACT_SCRIPT)
        return raw_items

    def _clean_data(self, raw_items: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        데이터 정리, 중복 제거, 링크 생성

        Args:
            raw_items: 추출된 raw 데이터 리스트

        Returns:
            정리된 DataFrame
        """
        data = []
        doc_numbers_set = set()

        for item in raw_items:
            if 'error' in item:
                continue

            doc_number = item.get('docNumber', '')
            if doc_number and doc_number not in doc_numbers_set:
                doc_numbers_set.add(doc_number)

                # Hook Method 호출: 서브클래스에서 구현
                link = self._generate_link(doc_number)

                data.append({
                    "세목": item.get('taxLabel', ''),
                    "생산일자": item.get('productionDate', ''),
                    "문서번호": doc_number,
                    "제목": item.get('title', ''),
                    "링크": link or ''
                })

        df = pd.DataFrame(data, columns=self.data_columns)

        # 전처리 및 후처리 적용
        df = self.preprocess_data(df)
        df = self.postprocess_data(df)

        self.logger.info(f"{self.site_name}: 총 {len(raw_items)}개 항목 중 {len(df)}개 고유 항목 수집 완료")

        return df

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        NTS 데이터 특화 검증

        Args:
            data: 검증할 DataFrame

        Returns:
            유효성 여부
        """
        if not super().validate_data(data):
            return False

        # NTS 특화 검증: 필수 컬럼 존재 확인
        required_columns = ["세목", "생산일자", "문서번호", "제목"]
        for col in required_columns:
            if col not in data.columns:
                return False

        # 문서번호 형식 검증
        if not data["문서번호"].str.len().gt(0).any():
            return False

        return True

    # =========================================================================
    # Hook Method: 서브클래스에서 구현
    # =========================================================================

    @abstractmethod
    def _generate_link(self, doc_number: str) -> str:
        """
        Hook Method: 문서번호로부터 링크 URL 생성

        서브클래스에서 반드시 구현해야 하는 메서드.
        Authority와 Precedent는 다른 링크 생성 방식 사용.

        Args:
            doc_number: 문서번호

        Returns:
            링크 URL 문자열
        """
        pass
