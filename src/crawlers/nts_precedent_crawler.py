"""
국세청 판례 크롤러

NTSBaseCrawler를 상속받아 _generate_link 훅 메서드만 구현.
기존 190줄 → 약 30줄로 축소 (Template Method 패턴 적용)
"""

from src.crawlers.nts_base_crawler import NTSBaseCrawler
from src.utils.link_generator import generate_nts_search_link


class NTSPrecedentCrawler(NTSBaseCrawler):
    """
    국세청 판례 크롤러

    동적 JavaScript 사이트에서 "더보기" 버튼을 통해 데이터를 로드하며,
    대량의 판례 데이터를 효율적으로 수집

    상위 클래스 NTSBaseCrawler에서 제공:
    - crawl(): Template Method
    - _load_data(): 더보기 버튼 클릭 로직
    - _extract_data(): JavaScript DOM 추출
    - _clean_data(): 데이터 정리 및 중복 제거
    - validate_data(): 데이터 검증

    이 클래스에서 구현:
    - _generate_link(): 판례 링크 생성
    """

    def __init__(self):
        super().__init__("국세청 판례", "nts_precedent")

    def _generate_link(self, doc_number: str) -> str:
        """
        Hook Method: 판례 문서번호로 검색 링크 생성

        Args:
            doc_number: 문서번호

        Returns:
            국세청 검색 결과 링크 URL
        """
        return generate_nts_search_link(doc_number, "precedent")
