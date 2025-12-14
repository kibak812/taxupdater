"""
크롤링 오케스트레이터 테스트

CrawlOrchestrator가 크롤러, 저장소, 알림 디스패처를
올바르게 조율하는지 검증
"""

import pytest
import pandas as pd
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.core.domain.crawl_result import CrawlResult, CrawlStatistics, CrawlStatus


class TestCrawlOrchestratorInterface:
    """CrawlOrchestrator 인터페이스 테스트"""

    def test_orchestrator_has_required_methods(self):
        """필수 메서드 존재 확인"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={},
            repository=Mock(),
            notification_dispatcher=Mock()
        )

        assert hasattr(orchestrator, 'execute_crawl')
        assert hasattr(orchestrator, 'get_available_sites')
        assert callable(orchestrator.execute_crawl)
        assert callable(orchestrator.get_available_sites)

    def test_orchestrator_stores_dependencies(self):
        """의존성 저장 확인"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        mock_crawler = Mock()
        mock_repository = Mock()
        mock_dispatcher = Mock()

        orchestrator = CrawlOrchestrator(
            crawlers={"test": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        assert "test" in orchestrator.get_available_sites()


class TestCrawlOrchestratorBehavior:
    """CrawlOrchestrator 동작 테스트"""

    @pytest.fixture
    def mock_crawler(self):
        """모의 크롤러"""
        crawler = Mock()
        crawler.get_site_key.return_value = "test_site"
        crawler.get_key_column.return_value = "문서번호"
        crawler.crawl.return_value = pd.DataFrame({
            "문서번호": ["DOC001", "DOC002", "DOC003"],
            "제목": ["제목1", "제목2", "제목3"]
        })
        return crawler

    @pytest.fixture
    def mock_repository(self):
        """모의 저장소"""
        repository = Mock()
        repository.load_existing_data.return_value = pd.DataFrame({
            "문서번호": ["DOC001"],  # 기존 데이터 1건
            "제목": ["제목1"]
        })
        repository.save_data.return_value = True
        return repository

    @pytest.fixture
    def mock_dispatcher(self):
        """모의 알림 디스패처"""
        dispatcher = Mock()
        dispatcher.dispatch_new_data = AsyncMock(return_value={"email": True})
        dispatcher.dispatch_error = AsyncMock(return_value={"email": True})
        return dispatcher

    @pytest.mark.asyncio
    async def test_execute_crawl_success(self, mock_crawler, mock_repository, mock_dispatcher):
        """성공적인 크롤링 실행"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        result = await orchestrator.execute_crawl("test_site")

        assert result.status == CrawlStatus.SUCCESS
        assert result.site_key == "test_site"
        mock_crawler.crawl.assert_called_once()

    @pytest.mark.asyncio
    async def test_detects_new_entries(self, mock_crawler, mock_repository, mock_dispatcher):
        """새 데이터 탐지"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        result = await orchestrator.execute_crawl("test_site")

        # DOC001은 기존, DOC002/DOC003은 신규
        assert result.statistics.new_count == 2
        assert result.statistics.existing_count == 1
        assert result.statistics.total_crawled == 3

    @pytest.mark.asyncio
    async def test_saves_new_entries(self, mock_crawler, mock_repository, mock_dispatcher):
        """새 데이터 저장"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        await orchestrator.execute_crawl("test_site")

        # 새 데이터가 저장되었는지 확인
        mock_repository.save_data.assert_called_once()
        call_args = mock_repository.save_data.call_args
        saved_df = call_args[0][1]  # 두 번째 인자가 DataFrame
        assert len(saved_df) == 2  # DOC002, DOC003

    @pytest.mark.asyncio
    async def test_dispatches_notification_on_new_data(self, mock_crawler, mock_repository, mock_dispatcher):
        """새 데이터 발견 시 알림 발송"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        await orchestrator.execute_crawl("test_site")

        mock_dispatcher.dispatch_new_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_notification_when_no_new_data(self, mock_crawler, mock_repository, mock_dispatcher):
        """새 데이터 없으면 알림 없음"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        # 기존 데이터와 동일한 데이터 반환
        mock_crawler.crawl.return_value = pd.DataFrame({
            "문서번호": ["DOC001"],
            "제목": ["제목1"]
        })

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        await orchestrator.execute_crawl("test_site")

        mock_dispatcher.dispatch_new_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_crawl_error(self, mock_repository, mock_dispatcher):
        """크롤링 에러 처리"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        error_crawler = Mock()
        error_crawler.get_site_key.return_value = "error_site"
        error_crawler.crawl.side_effect = Exception("Connection timeout")

        orchestrator = CrawlOrchestrator(
            crawlers={"error_site": error_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        result = await orchestrator.execute_crawl("error_site")

        assert result.status == CrawlStatus.ERROR
        assert "Connection timeout" in result.error_message
        mock_dispatcher.dispatch_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_site_raises_error(self, mock_repository, mock_dispatcher):
        """알 수 없는 사이트 에러"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        with pytest.raises(KeyError):
            await orchestrator.execute_crawl("unknown_site")

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_crawler(self, mock_crawler, mock_repository, mock_dispatcher):
        """kwargs가 크롤러에 전달됨"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            crawlers={"test_site": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=mock_dispatcher
        )

        await orchestrator.execute_crawl(
            "test_site",
            max_items=100,
            progress_callback=Mock()
        )

        call_kwargs = mock_crawler.crawl.call_args[1]
        assert call_kwargs.get('max_items') == 100
        assert 'progress_callback' in call_kwargs


class TestCrawlOrchestratorCallbacks:
    """CrawlOrchestrator 콜백 테스트"""

    @pytest.mark.asyncio
    async def test_progress_callback_forwarded(self):
        """진행률 콜백 전달"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        progress_values = []

        def track_progress(value):
            progress_values.append(value)

        mock_crawler = Mock()
        mock_crawler.get_site_key.return_value = "test"
        mock_crawler.get_key_column.return_value = "id"
        mock_crawler.crawl.return_value = pd.DataFrame({"id": []})

        mock_repository = Mock()
        mock_repository.load_existing_data.return_value = pd.DataFrame({"id": []})

        orchestrator = CrawlOrchestrator(
            crawlers={"test": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=Mock()
        )

        await orchestrator.execute_crawl("test", progress_callback=track_progress)

        # 크롤러에 콜백이 전달되었는지 확인
        call_kwargs = mock_crawler.crawl.call_args[1]
        assert 'progress_callback' in call_kwargs

    @pytest.mark.asyncio
    async def test_status_callback_forwarded(self):
        """상태 콜백 전달"""
        from src.core.services.crawl_orchestrator import CrawlOrchestrator

        status_messages = []

        def track_status(msg):
            status_messages.append(msg)

        mock_crawler = Mock()
        mock_crawler.get_site_key.return_value = "test"
        mock_crawler.get_key_column.return_value = "id"
        mock_crawler.crawl.return_value = pd.DataFrame({"id": []})

        mock_repository = Mock()
        mock_repository.load_existing_data.return_value = pd.DataFrame({"id": []})

        orchestrator = CrawlOrchestrator(
            crawlers={"test": mock_crawler},
            repository=mock_repository,
            notification_dispatcher=Mock()
        )

        await orchestrator.execute_crawl("test", status_callback=track_status)

        call_kwargs = mock_crawler.crawl.call_args[1]
        assert 'status_callback' in call_kwargs


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
