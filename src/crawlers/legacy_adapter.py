"""
레거시 함수형 크롤러 어댑터 (Adapter 패턴)

GPT-5.2 권장사항 반영:
- 함수형 크롤러를 클래스로 변환하지 않고 어댑터로 래핑
- ICrawler 인터페이스 만족
- 기존 함수의 시그니처 그대로 유지

사용 예:
    from src.crawlers.legacy_adapter import LegacyCrawlerAdapter
    from src.crawlers.web_legacy_crawlers import crawl_moef_site

    moef_crawler = LegacyCrawlerAdapter(
        site_key="moef",
        crawl_func=crawl_moef_site,
        key_column="문서번호"
    )
    result = moef_crawler.crawl(max_pages=10)
"""

import pandas as pd
from typing import Callable, Optional, Any

from src.core.ports.crawler_port import ICrawler
from src.config.sites import get_site, get_display


class LegacyCrawlerAdapter(ICrawler):
    """
    함수형 크롤러를 ICrawler 인터페이스로 어댑트

    기존 함수형 크롤러(crawl_moef_site, crawl_mois_site, crawl_bai_site)를
    클래스로 변환하지 않고 ICrawler 인터페이스에 맞게 래핑합니다.

    Attributes:
        site_key: 사이트 식별자
        _crawl_func: 래핑할 크롤링 함수
        _key_column: 중복 제거용 키 컬럼명
    """

    def __init__(
        self,
        site_key: str,
        crawl_func: Callable[..., pd.DataFrame],
        key_column: Optional[str] = None
    ):
        """
        어댑터 초기화

        Args:
            site_key: 사이트 식별자 (예: "moef", "mois", "bai")
            crawl_func: 래핑할 크롤링 함수
            key_column: 키 컬럼명 (None이면 SiteCatalog에서 조회)
        """
        self.site_key = site_key
        self._crawl_func = crawl_func

        # 키 컬럼: 명시적 지정 또는 SiteCatalog에서 조회
        if key_column is not None:
            self._key_column = key_column
        else:
            try:
                site_def = get_site(site_key)
                self._key_column = site_def.key_column
            except KeyError:
                self._key_column = "문서번호"  # 기본값

    def crawl(
        self,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        ICrawler.crawl 구현 - 래핑된 함수 호출

        레거시 함수의 파라미터 시그니처에 맞게 변환:
        - progress_callback → progress
        - status_callback → status_message

        Args:
            progress_callback: 진행률 콜백 (0-100)
            status_callback: 상태 메시지 콜백
            **kwargs: 크롤러별 추가 옵션

        Returns:
            크롤링 결과 DataFrame
        """
        # 레거시 함수 시그니처에 맞게 파라미터 변환
        # 레거시 함수들은 progress와 status_message 파라미터를 사용
        result = self._crawl_func(
            progress=self._wrap_progress(progress_callback),
            status_message=self._wrap_status(status_callback),
            **kwargs
        )

        # 결과가 None인 경우 빈 DataFrame 반환
        if result is None:
            return pd.DataFrame()

        return result

    def get_key_column(self) -> str:
        """ICrawler.get_key_column 구현"""
        return self._key_column

    def get_site_key(self) -> str:
        """ICrawler.get_site_key 구현"""
        return self.site_key

    def get_site_name(self) -> str:
        """
        사이트의 한글 표시명 반환

        Returns:
            사이트 한글명 (예: "기획재정부", "행정안전부", "감사원")
        """
        try:
            display = get_display(self.site_key)
            return display.name
        except KeyError:
            # 기본값: site_key 반환
            return self.site_key

    def _wrap_progress(self, callback: Optional[Callable[[int], None]]) -> Any:
        """
        진행률 콜백을 레거시 progress 객체로 래핑

        레거시 함수들은 progress.value 속성과 progress.update() 메서드를 기대
        """
        if callback is None:
            return None

        class ProgressWrapper:
            def __init__(self, cb):
                self._callback = cb
                self._value = 0

            @property
            def value(self):
                return self._value

            @value.setter
            def value(self, val):
                self._value = val
                if self._callback:
                    self._callback(val)

            def update(self):
                pass

        return ProgressWrapper(callback)

    def _wrap_status(self, callback: Optional[Callable[[str], None]]) -> Any:
        """
        상태 콜백을 레거시 status_message 객체로 래핑

        레거시 함수들은 status_message.config(text=...) 메서드를 기대
        """
        if callback is None:
            return None

        class StatusWrapper:
            def __init__(self, cb):
                self._callback = cb
                self.text = ""

            def config(self, text=""):
                self.text = text
                if self._callback:
                    self._callback(text)

            def update(self):
                pass

        return StatusWrapper(callback)


# =============================================================================
# 편의 함수: 사전 구성된 어댑터 생성
# =============================================================================

def create_moef_adapter() -> LegacyCrawlerAdapter:
    """기획재정부 크롤러 어댑터 생성"""
    from src.crawlers.web_legacy_crawlers import crawl_moef_site
    return LegacyCrawlerAdapter(
        site_key="moef",
        crawl_func=crawl_moef_site,
        key_column="문서번호"
    )


def create_mois_adapter() -> LegacyCrawlerAdapter:
    """행정안전부 크롤러 어댑터 생성"""
    from src.crawlers.web_legacy_crawlers import crawl_mois_site
    return LegacyCrawlerAdapter(
        site_key="mois",
        crawl_func=crawl_mois_site,
        key_column="문서번호"
    )


def create_bai_adapter() -> LegacyCrawlerAdapter:
    """감사원 크롤러 어댑터 생성"""
    from src.crawlers.web_legacy_crawlers import crawl_bai_site
    return LegacyCrawlerAdapter(
        site_key="bai",
        crawl_func=crawl_bai_site,
        key_column="문서번호"
    )
