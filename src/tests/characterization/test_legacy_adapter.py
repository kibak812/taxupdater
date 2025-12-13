"""
LegacyCrawlerAdapter 테스트

Adapter 패턴이 ICrawler 인터페이스를 올바르게 구현하는지 검증
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock


class TestLegacyCrawlerAdapterInterface:
    """LegacyCrawlerAdapter ICrawler 인터페이스 준수 테스트"""

    def test_adapter_has_crawl_method(self):
        """crawl 메서드 존재 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        assert hasattr(adapter, 'crawl')
        assert callable(adapter.crawl)

    def test_adapter_has_get_key_column_method(self):
        """get_key_column 메서드 존재 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        assert hasattr(adapter, 'get_key_column')
        assert callable(adapter.get_key_column)

    def test_adapter_has_get_site_key_method(self):
        """get_site_key 메서드 존재 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        assert hasattr(adapter, 'get_site_key')
        assert callable(adapter.get_site_key)

    def test_adapter_has_validate_data_method(self):
        """validate_data 메서드 존재 확인 (ICrawler 기본 구현)"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        assert hasattr(adapter, 'validate_data')
        assert callable(adapter.validate_data)


class TestLegacyCrawlerAdapterBehavior:
    """LegacyCrawlerAdapter 동작 테스트"""

    def test_crawl_calls_underlying_function(self):
        """crawl 호출 시 래핑된 함수가 호출되는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_df = pd.DataFrame({"col1": [1, 2, 3]})
        mock_func = Mock(return_value=mock_df)

        adapter = LegacyCrawlerAdapter("test", mock_func, "col1")
        result = adapter.crawl()

        mock_func.assert_called_once()
        assert result.equals(mock_df)

    def test_crawl_passes_kwargs(self):
        """crawl 호출 시 kwargs가 전달되는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        adapter.crawl(max_pages=10, max_items=500)

        # kwargs가 전달되었는지 확인
        call_kwargs = mock_func.call_args.kwargs
        assert call_kwargs.get('max_pages') == 10
        assert call_kwargs.get('max_items') == 500

    def test_get_key_column_returns_configured_value(self):
        """get_key_column이 설정된 값을 반환하는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "문서번호")

        assert adapter.get_key_column() == "문서번호"

    def test_get_site_key_returns_configured_value(self):
        """get_site_key가 설정된 값을 반환하는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("moef", mock_func, "문서번호")

        assert adapter.get_site_key() == "moef"

    def test_crawl_returns_empty_dataframe_when_func_returns_none(self):
        """래핑된 함수가 None 반환 시 빈 DataFrame 반환"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=None)
        adapter = LegacyCrawlerAdapter("test", mock_func, "key_col")

        result = adapter.crawl()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestProgressAndStatusWrapper:
    """Progress/Status 래퍼 테스트"""

    def test_progress_callback_is_called(self):
        """진행률 콜백이 호출되는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        progress_values = []

        def capture_progress(val):
            progress_values.append(val)

        def mock_crawl_func(progress=None, status_message=None, **kwargs):
            if progress:
                progress.value = 50
                progress.value = 100
            return pd.DataFrame({"col1": [1]})

        adapter = LegacyCrawlerAdapter("test", mock_crawl_func, "col1")
        adapter.crawl(progress_callback=capture_progress)

        assert 50 in progress_values
        assert 100 in progress_values

    def test_status_callback_is_called(self):
        """상태 콜백이 호출되는지 확인"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        status_messages = []

        def capture_status(msg):
            status_messages.append(msg)

        def mock_crawl_func(progress=None, status_message=None, **kwargs):
            if status_message:
                status_message.config(text="크롤링 시작")
                status_message.config(text="크롤링 완료")
            return pd.DataFrame({"col1": [1]})

        adapter = LegacyCrawlerAdapter("test", mock_crawl_func, "col1")
        adapter.crawl(status_callback=capture_status)

        assert "크롤링 시작" in status_messages
        assert "크롤링 완료" in status_messages


class TestValidateData:
    """ICrawler.validate_data 기본 구현 테스트"""

    def test_validate_data_returns_true_for_valid_data(self):
        """유효한 데이터에 대해 True 반환"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "문서번호")

        valid_data = pd.DataFrame({
            "문서번호": ["DOC-001", "DOC-002"],
            "제목": ["제목1", "제목2"]
        })

        assert adapter.validate_data(valid_data) is True

    def test_validate_data_returns_false_for_empty_data(self):
        """빈 데이터에 대해 False 반환"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "문서번호")

        assert adapter.validate_data(pd.DataFrame()) is False

    def test_validate_data_returns_false_for_missing_key_column(self):
        """키 컬럼 누락 시 False 반환"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "문서번호")

        data_without_key = pd.DataFrame({
            "제목": ["제목1", "제목2"]
        })

        assert adapter.validate_data(data_without_key) is False

    def test_validate_data_returns_false_for_empty_key_values(self):
        """키 컬럼에 빈 값이 있으면 False 반환"""
        from src.crawlers.legacy_adapter import LegacyCrawlerAdapter

        mock_func = Mock(return_value=pd.DataFrame())
        adapter = LegacyCrawlerAdapter("test", mock_func, "문서번호")

        data_with_empty_key = pd.DataFrame({
            "문서번호": ["DOC-001", ""],
            "제목": ["제목1", "제목2"]
        })

        assert adapter.validate_data(data_with_empty_key) is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
