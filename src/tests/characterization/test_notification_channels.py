"""
알림 채널 테스트

EmailChannel과 WebSocketChannel이 INotificationChannel 인터페이스를
올바르게 구현하는지 검증
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.core.domain.crawl_result import CrawlResult, CrawlStatistics, CrawlStatus


class TestEmailChannelInterface:
    """EmailChannel INotificationChannel 인터페이스 준수 테스트"""

    def test_channel_has_required_properties(self):
        """필수 프로퍼티 존재 확인"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel()

        assert hasattr(channel, 'channel_name')
        assert hasattr(channel, 'is_enabled')
        assert channel.channel_name == "email"

    def test_channel_has_required_methods(self):
        """필수 메서드 존재 확인"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel()

        assert hasattr(channel, 'send_new_data_notification')
        assert hasattr(channel, 'send_error_notification')
        assert callable(channel.send_new_data_notification)
        assert callable(channel.send_error_notification)

    def test_channel_enabled_by_default(self):
        """기본적으로 활성화되어 있는지 확인"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel(enabled=True)
        assert channel.is_enabled is True

    def test_channel_can_be_disabled(self):
        """비활성화 가능한지 확인"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel(enabled=False)
        assert channel.is_enabled is False


class TestEmailChannelBehavior:
    """EmailChannel 동작 테스트"""

    @pytest.mark.asyncio
    async def test_returns_true_when_disabled(self):
        """비활성화 시 True 반환"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel(enabled=False)

        result = CrawlResult.success(
            site_key="test",
            statistics=CrawlStatistics(10, 5, 5, 0)
        )

        success = await channel.send_new_data_notification(result)
        assert success is True

    @pytest.mark.asyncio
    async def test_returns_true_when_no_new_data(self):
        """새 데이터가 없을 때 True 반환"""
        from src.services.notifications.email_channel import EmailChannel

        channel = EmailChannel(enabled=True)

        result = CrawlResult.success(
            site_key="test",
            statistics=CrawlStatistics(10, 0, 10, 0)  # new_count=0
        )

        success = await channel.send_new_data_notification(result)
        assert success is True

    @pytest.mark.asyncio
    async def test_returns_true_when_no_email_settings(self):
        """이메일 설정이 없을 때 True 반환"""
        from src.services.notifications.email_channel import EmailChannel

        async def no_settings():
            return []

        channel = EmailChannel(get_email_settings=no_settings, enabled=True)

        result = CrawlResult.success(
            site_key="tax_tribunal",
            statistics=CrawlStatistics(10, 5, 5, 0)
        )

        success = await channel.send_new_data_notification(result)
        assert success is True


class TestWebSocketChannelInterface:
    """WebSocketChannel INotificationChannel 인터페이스 준수 테스트"""

    def test_channel_has_required_properties(self):
        """필수 프로퍼티 존재 확인"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        channel = WebSocketChannel()

        assert hasattr(channel, 'channel_name')
        assert hasattr(channel, 'is_enabled')
        assert channel.channel_name == "websocket"

    def test_channel_has_required_methods(self):
        """필수 메서드 존재 확인"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        channel = WebSocketChannel()

        assert hasattr(channel, 'send_new_data_notification')
        assert hasattr(channel, 'send_error_notification')
        assert hasattr(channel, 'send_status_update')
        assert callable(channel.send_new_data_notification)
        assert callable(channel.send_error_notification)
        assert callable(channel.send_status_update)

    def test_channel_disabled_without_manager(self):
        """매니저 없이는 비활성화"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        channel = WebSocketChannel(connection_manager=None, enabled=True)
        assert channel.is_enabled is False

    def test_channel_enabled_with_manager(self):
        """매니저 있으면 활성화"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)
        assert channel.is_enabled is True


class TestWebSocketChannelBehavior:
    """WebSocketChannel 동작 테스트"""

    @pytest.mark.asyncio
    async def test_broadcasts_new_data_notification(self):
        """새 데이터 알림 브로드캐스트"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)

        result = CrawlResult.success(
            site_key="tax_tribunal",
            statistics=CrawlStatistics(100, 10, 90, 0)
        )

        success = await channel.send_new_data_notification(result)

        assert success is True
        mock_manager.broadcast.assert_called_once()

        # 브로드캐스트 메시지 검증
        call_args = mock_manager.broadcast.call_args[0][0]
        assert call_args['type'] == 'new_data'
        assert call_args['site_key'] == 'tax_tribunal'
        assert call_args['new_count'] == 10

    @pytest.mark.asyncio
    async def test_broadcasts_error_notification(self):
        """에러 알림 브로드캐스트"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)

        result = CrawlResult.error(
            site_key="tax_tribunal",
            error_message="Connection timeout"
        )

        success = await channel.send_error_notification(result)

        assert success is True
        mock_manager.broadcast.assert_called_once()

        call_args = mock_manager.broadcast.call_args[0][0]
        assert call_args['type'] == 'error'
        assert 'Connection timeout' in call_args['message']

    @pytest.mark.asyncio
    async def test_broadcasts_status_update(self):
        """상태 업데이트 브로드캐스트"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)

        success = await channel.send_status_update(
            site_key="tax_tribunal",
            status="crawling",
            message="크롤링 진행 중..."
        )

        assert success is True
        mock_manager.broadcast.assert_called_once()

        call_args = mock_manager.broadcast.call_args[0][0]
        assert call_args['type'] == 'status'
        assert call_args['status'] == 'crawling'

    @pytest.mark.asyncio
    async def test_returns_true_when_no_new_data(self):
        """새 데이터 없을 때 브로드캐스트 안함"""
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)

        result = CrawlResult.success(
            site_key="tax_tribunal",
            statistics=CrawlStatistics(100, 0, 100, 0)
        )

        success = await channel.send_new_data_notification(result)

        assert success is True
        mock_manager.broadcast.assert_not_called()


class TestNotificationDispatcher:
    """NotificationDispatcher 테스트"""

    def test_dispatcher_has_required_methods(self):
        """필수 메서드 존재 확인"""
        from src.services.notifications.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()

        assert hasattr(dispatcher, 'dispatch_new_data')
        assert hasattr(dispatcher, 'dispatch_error')
        assert hasattr(dispatcher, 'dispatch_status')
        assert hasattr(dispatcher, 'active_channels')

    def test_dispatcher_tracks_active_channels(self):
        """활성 채널 추적"""
        from src.services.notifications.dispatcher import NotificationDispatcher
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        ws_channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)

        dispatcher = NotificationDispatcher([ws_channel])

        assert "websocket" in dispatcher.active_channels

    def test_dispatcher_can_add_channels(self):
        """채널 추가 가능"""
        from src.services.notifications.dispatcher import NotificationDispatcher
        from src.services.notifications.websocket_channel import WebSocketChannel

        dispatcher = NotificationDispatcher()
        assert len(dispatcher.active_channels) == 0

        mock_manager = Mock()
        ws_channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)
        dispatcher.add_channel(ws_channel)

        assert "websocket" in dispatcher.active_channels

    @pytest.mark.asyncio
    async def test_dispatch_new_data_to_all_channels(self):
        """새 데이터 알림을 모든 채널로 발송"""
        from src.services.notifications.dispatcher import NotificationDispatcher
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        ws_channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)
        dispatcher = NotificationDispatcher([ws_channel])

        result = CrawlResult.success(
            site_key="tax_tribunal",
            statistics=CrawlStatistics(100, 10, 90, 0)
        )

        results = await dispatcher.dispatch_new_data(result)

        assert results.get("websocket") is True
        mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_returns_empty_when_no_new_data(self):
        """새 데이터 없으면 빈 결과 반환"""
        from src.services.notifications.dispatcher import NotificationDispatcher
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        ws_channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)
        dispatcher = NotificationDispatcher([ws_channel])

        result = CrawlResult.success(
            site_key="tax_tribunal",
            statistics=CrawlStatistics(100, 0, 100, 0)  # no new data
        )

        results = await dispatcher.dispatch_new_data(result)

        assert results == {}
        mock_manager.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_error_to_all_channels(self):
        """에러 알림을 모든 채널로 발송"""
        from src.services.notifications.dispatcher import NotificationDispatcher
        from src.services.notifications.websocket_channel import WebSocketChannel

        mock_manager = Mock()
        mock_manager.broadcast = AsyncMock()

        ws_channel = WebSocketChannel(connection_manager=mock_manager, enabled=True)
        dispatcher = NotificationDispatcher([ws_channel])

        result = CrawlResult.error(
            site_key="tax_tribunal",
            error_message="Connection failed"
        )

        results = await dispatcher.dispatch_error(result)

        assert results.get("websocket") is True
        mock_manager.broadcast.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
