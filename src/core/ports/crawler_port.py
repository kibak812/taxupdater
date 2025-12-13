"""
크롤러 포트 인터페이스

Hexagonal Architecture의 포트 정의:
- ICrawler: 모든 크롤러가 구현해야 하는 인터페이스
- 도메인 코어는 이 인터페이스에만 의존, 구체적인 크롤러 구현에 의존하지 않음
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Any
import pandas as pd


class ICrawler(ABC):
    """
    크롤러 인터페이스 (Port)

    모든 크롤러 구현체는 이 인터페이스를 만족해야 함:
    - 클래스 기반 크롤러: 직접 구현
    - 함수 기반 크롤러: LegacyCrawlerAdapter를 통해 구현

    사용 예:
        crawler: ICrawler = NTSAuthorityCrawler()
        result = crawler.crawl(progress_callback=update_progress)
        key_col = crawler.get_key_column()
    """

    @abstractmethod
    def crawl(
        self,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        크롤링 실행

        Args:
            progress_callback: 진행률 콜백 (0-100 정수)
            status_callback: 상태 메시지 콜백
            **kwargs: 크롤러별 추가 옵션 (max_items, max_pages 등)

        Returns:
            크롤링 결과 DataFrame

        Raises:
            CrawlError: 크롤링 실패 시
        """
        pass

    @abstractmethod
    def get_key_column(self) -> str:
        """
        중복 제거용 키 컬럼명 반환

        Returns:
            키 컬럼명 (예: "문서번호", "청구번호")
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        크롤링 결과 유효성 검증

        기본 구현: 데이터가 비어있지 않고, 키 컬럼이 존재하며,
                  키 컬럼에 빈 값이 없는지 확인

        Args:
            data: 검증할 DataFrame

        Returns:
            유효성 여부
        """
        if data is None or data.empty:
            return False

        key_column = self.get_key_column()
        if key_column not in data.columns:
            return False

        # 키 컬럼에 빈 값이 없어야 함
        if data[key_column].isna().any() or (data[key_column] == '').any():
            return False

        return True

    def get_site_key(self) -> str:
        """
        사이트 키 반환

        기본 구현: 인스턴스 속성에서 조회
        서브클래스에서 오버라이드하거나 self.site_key 속성 설정

        Returns:
            사이트 식별자 (예: "tax_tribunal", "nts_authority")
        """
        # BaseCrawler와 호환: site_key 속성 또는 _site_key 속성에서 조회
        return getattr(self, 'site_key', getattr(self, '_site_key', 'unknown'))


class CrawlError(Exception):
    """크롤링 실패 예외"""

    def __init__(self, site_key: str, message: str, original_error: Optional[Exception] = None):
        self.site_key = site_key
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{site_key}] {message}")
