"""
캐릭터라이제이션 테스트: NTS 크롤러 출력 형식 고정

이 테스트는 리팩토링 전 현재 동작을 캡처합니다.
Template Method 패턴 적용 후에도 동일한 출력 형식을 보장합니다.

실행 방법:
    pytest src/tests/characterization/test_nts_crawler_output.py -v
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class TestNTSCrawlerOutputFormat:
    """NTS 크롤러 출력 형식 캐릭터라이제이션 테스트"""

    # 예상 컬럼 정의 (현재 동작 고정)
    NTS_AUTHORITY_COLUMNS = ["세목", "생산일자", "문서번호", "제목", "링크"]
    NTS_PRECEDENT_COLUMNS = ["세목", "생산일자", "문서번호", "제목", "링크"]

    def test_nts_authority_output_columns(self):
        """NTS Authority 크롤러 출력 컬럼 형식 고정"""
        from src.config.settings import DATA_COLUMNS

        # 현재 설정된 컬럼이 예상과 일치하는지 확인
        assert DATA_COLUMNS["nts_authority"] == self.NTS_AUTHORITY_COLUMNS, \
            f"NTS Authority 컬럼이 변경됨: {DATA_COLUMNS['nts_authority']}"

    def test_nts_precedent_output_columns(self):
        """NTS Precedent 크롤러 출력 컬럼 형식 고정"""
        from src.config.settings import DATA_COLUMNS

        # 현재 설정된 컬럼이 예상과 일치하는지 확인
        assert DATA_COLUMNS["nts_precedent"] == self.NTS_PRECEDENT_COLUMNS, \
            f"NTS Precedent 컬럼이 변경됨: {DATA_COLUMNS['nts_precedent']}"

    def test_nts_authority_key_column(self):
        """NTS Authority 키 컬럼 고정"""
        from src.config.settings import KEY_COLUMNS

        assert KEY_COLUMNS["nts_authority"] == "문서번호", \
            f"NTS Authority 키 컬럼이 변경됨: {KEY_COLUMNS['nts_authority']}"

    def test_nts_precedent_key_column(self):
        """NTS Precedent 키 컬럼 고정"""
        from src.config.settings import KEY_COLUMNS

        assert KEY_COLUMNS["nts_precedent"] == "문서번호", \
            f"NTS Precedent 키 컬럼이 변경됨: {KEY_COLUMNS['nts_precedent']}"


class TestNTSCrawlerCleanDataBehavior:
    """NTS 크롤러 _clean_data 메서드 동작 테스트"""

    @pytest.fixture
    def mock_raw_items(self):
        """테스트용 raw 데이터"""
        return [
            {
                'taxLabel': '법인세',
                'productionDate': '2024-01-15',
                'docNumber': 'ABC-2024-001',
                'title': '테스트 유권해석 1'
            },
            {
                'taxLabel': '소득세',
                'productionDate': '2024-01-16',
                'docNumber': 'ABC-2024-002',
                'title': '테스트 유권해석 2'
            },
            # 중복 문서번호 (필터링되어야 함)
            {
                'taxLabel': '법인세',
                'productionDate': '2024-01-17',
                'docNumber': 'ABC-2024-001',
                'title': '중복 문서'
            },
            # 에러 항목 (필터링되어야 함)
            {
                'error': 'Some error'
            }
        ]

    @patch('src.crawlers.nts_authority_crawler.generate_nts_search_link')
    def test_authority_clean_data_filters_duplicates(self, mock_link_gen, mock_raw_items):
        """Authority 크롤러: 중복 문서번호 필터링 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        mock_link_gen.return_value = 'https://example.com/link'

        crawler = NTSAuthorityCrawler()
        result = crawler._clean_data(mock_raw_items)

        # 중복 제거 후 2개만 남아야 함
        assert len(result) == 2, f"중복 제거 실패: {len(result)}개 결과"

        # 문서번호가 고유한지 확인
        assert result['문서번호'].nunique() == len(result), "중복 문서번호가 있음"

    @patch('src.crawlers.nts_authority_crawler.generate_nts_search_link')
    def test_authority_clean_data_filters_errors(self, mock_link_gen, mock_raw_items):
        """Authority 크롤러: 에러 항목 필터링 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        mock_link_gen.return_value = 'https://example.com/link'

        crawler = NTSAuthorityCrawler()
        result = crawler._clean_data(mock_raw_items)

        # 에러 항목은 포함되지 않아야 함
        assert 'error' not in result.columns, "에러 컬럼이 결과에 포함됨"

    @patch('src.crawlers.nts_authority_crawler.generate_nts_search_link')
    def test_authority_clean_data_output_format(self, mock_link_gen, mock_raw_items):
        """Authority 크롤러: 출력 DataFrame 형식 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        mock_link_gen.return_value = 'https://example.com/link'

        crawler = NTSAuthorityCrawler()
        result = crawler._clean_data(mock_raw_items)

        # DataFrame 타입 확인
        assert isinstance(result, pd.DataFrame), "결과가 DataFrame이 아님"

        # 컬럼 형식 확인
        expected_columns = ["세목", "생산일자", "문서번호", "제목", "링크"]
        assert list(result.columns) == expected_columns, \
            f"컬럼 형식 불일치: {list(result.columns)}"

    @patch('src.crawlers.nts_authority_crawler.generate_nts_search_link')
    def test_authority_link_generation_called(self, mock_link_gen, mock_raw_items):
        """Authority 크롤러: 링크 생성 함수 호출 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        mock_link_gen.return_value = 'https://example.com/link'

        crawler = NTSAuthorityCrawler()
        crawler._clean_data(mock_raw_items)

        # 유효한 문서번호에 대해 링크 생성 호출됨
        assert mock_link_gen.call_count == 2, \
            f"링크 생성이 {mock_link_gen.call_count}번 호출됨 (예상: 2번)"

        # 호출 인자 확인
        calls = mock_link_gen.call_args_list
        assert calls[0][0] == ('ABC-2024-001', 'authority')
        assert calls[1][0] == ('ABC-2024-002', 'authority')


class TestNTSCrawlerValidation:
    """NTS 크롤러 데이터 검증 테스트"""

    def test_authority_validate_data_with_valid_data(self):
        """유효한 데이터 검증 통과 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        crawler = NTSAuthorityCrawler()

        valid_data = pd.DataFrame({
            '세목': ['법인세'],
            '생산일자': ['2024-01-15'],
            '문서번호': ['ABC-2024-001'],
            '제목': ['테스트'],
            '링크': ['https://example.com']
        })

        assert crawler.validate_data(valid_data) is True, "유효한 데이터가 검증 실패"

    def test_authority_validate_data_with_missing_columns(self):
        """필수 컬럼 누락 시 검증 실패 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        crawler = NTSAuthorityCrawler()

        # 문서번호 컬럼 누락
        invalid_data = pd.DataFrame({
            '세목': ['법인세'],
            '생산일자': ['2024-01-15'],
            '제목': ['테스트'],
            '링크': ['https://example.com']
        })

        assert crawler.validate_data(invalid_data) is False, "필수 컬럼 누락 검증 실패"

    def test_authority_validate_data_with_empty_doc_number(self):
        """빈 문서번호 검증 실패 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        crawler = NTSAuthorityCrawler()

        invalid_data = pd.DataFrame({
            '세목': ['법인세'],
            '생산일자': ['2024-01-15'],
            '문서번호': [''],  # 빈 문서번호
            '제목': ['테스트'],
            '링크': ['https://example.com']
        })

        assert crawler.validate_data(invalid_data) is False, "빈 문서번호 검증 실패"


class TestNTSCrawlerInterface:
    """NTS 크롤러 인터페이스 테스트"""

    def test_authority_crawler_has_required_methods(self):
        """Authority 크롤러 필수 메서드 존재 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        crawler = NTSAuthorityCrawler()

        # 필수 메서드 확인
        assert hasattr(crawler, 'crawl'), "crawl 메서드 없음"
        assert hasattr(crawler, 'get_key_column'), "get_key_column 메서드 없음"
        assert hasattr(crawler, 'validate_data'), "validate_data 메서드 없음"
        assert hasattr(crawler, '_clean_data'), "_clean_data 메서드 없음"
        assert hasattr(crawler, '_load_data'), "_load_data 메서드 없음"
        assert hasattr(crawler, '_extract_data'), "_extract_data 메서드 없음"

    def test_precedent_crawler_has_required_methods(self):
        """Precedent 크롤러 필수 메서드 존재 확인"""
        from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler

        crawler = NTSPrecedentCrawler()

        # 필수 메서드 확인
        assert hasattr(crawler, 'crawl'), "crawl 메서드 없음"
        assert hasattr(crawler, 'get_key_column'), "get_key_column 메서드 없음"
        assert hasattr(crawler, 'validate_data'), "validate_data 메서드 없음"
        assert hasattr(crawler, '_clean_data'), "_clean_data 메서드 없음"
        assert hasattr(crawler, '_load_data'), "_load_data 메서드 없음"
        assert hasattr(crawler, '_extract_data'), "_extract_data 메서드 없음"

    def test_authority_get_key_column(self):
        """Authority 크롤러 키 컬럼 반환 확인"""
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler

        crawler = NTSAuthorityCrawler()
        assert crawler.get_key_column() == "문서번호"

    def test_precedent_get_key_column(self):
        """Precedent 크롤러 키 컬럼 반환 확인"""
        from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler

        crawler = NTSPrecedentCrawler()
        assert crawler.get_key_column() == "문서번호"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
