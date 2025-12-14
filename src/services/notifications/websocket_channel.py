"""
WebSocket 알림 채널 (Strategy 패턴)

GPT-5.2 권장사항 반영:
- 기존 notification_service.py에서 WebSocket 관련 로직만 분리
- INotificationChannel 인터페이스 구현
- 단일 책임: WebSocket 브로드캐스트만 담당

크기: 기존 ~200줄 → ~50줄
"""

from typing import Optional, Any
from datetime import datetime

from src.core.ports.notification_port import INotificationChannel
from src.core.domain.crawl_result import CrawlResult
from src.config.sites import SITE_DISPLAY
from src.config.logging_config import get_logger


class WebSocketChannel(INotificationChannel):
    """
    WebSocket 알림 채널

    ConnectionManager를 통해 연결된 모든 클라이언트에
    실시간으로 알림을 브로드캐스트합니다.

    사용 예:
        channel = WebSocketChannel(connection_manager=ws_manager)
        await channel.send_new_data_notification(result)
    """

    def __init__(
        self,
        connection_manager: Optional[Any] = None,
        enabled: bool = True
    ):
        """
        WebSocket 채널 초기화

        Args:
            connection_manager: WebSocket 연결 관리자 (broadcast 메서드 필요)
            enabled: 채널 활성화 여부
        """
        self._manager = connection_manager
        self._enabled = enabled
        self._logger = get_logger(__name__)

    @property
    def channel_name(self) -> str:
        return "websocket"

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._manager is not None

    def set_manager(self, manager: Any):
        """WebSocket 연결 관리자 설정 (지연 초기화용)"""
        self._manager = manager

    def set_enabled(self, enabled: bool):
        """채널 활성화/비활성화"""
        self._enabled = enabled

    async def send_new_data_notification(self, result: CrawlResult) -> bool:
        """
        새 데이터 발견 WebSocket 알림 브로드캐스트

        Args:
            result: 크롤링 결과

        Returns:
            발송 성공 여부
        """
        if not self.is_enabled:
            return True

        if not result.has_new_data:
            return True

        try:
            site_name = self._get_site_name(result.site_key)

            message = {
                "type": "new_data",
                "site_key": result.site_key,
                "site_name": site_name,
                "title": f"새로운 데이터 발견: {site_name}",
                "message": f"{result.statistics.new_count}개의 새로운 데이터가 발견되었습니다.",
                "new_count": result.statistics.new_count,
                "total_crawled": result.statistics.total_crawled,
                "timestamp": datetime.now().isoformat(),
                "urgency": "high" if result.statistics.new_count >= 10 else "normal"
            }

            await self._manager.broadcast(message)
            self._logger.info(f"WebSocket 알림 브로드캐스트: {result.site_key}")
            return True

        except Exception as e:
            self._logger.error(f"WebSocket 알림 브로드캐스트 실패: {e}")
            return False

    async def send_error_notification(self, result: CrawlResult) -> bool:
        """
        에러 알림 WebSocket 브로드캐스트

        Args:
            result: 에러가 발생한 크롤링 결과

        Returns:
            발송 성공 여부
        """
        if not self.is_enabled:
            return True

        try:
            site_name = self._get_site_name(result.site_key)

            message = {
                "type": "error",
                "site_key": result.site_key,
                "site_name": site_name,
                "title": f"크롤링 오류: {site_name}",
                "message": result.error_message or "알 수 없는 오류",
                "timestamp": datetime.now().isoformat(),
                "urgency": "high"
            }

            await self._manager.broadcast(message)
            self._logger.info(f"WebSocket 에러 알림 브로드캐스트: {result.site_key}")
            return True

        except Exception as e:
            self._logger.error(f"WebSocket 에러 알림 브로드캐스트 실패: {e}")
            return False

    async def send_status_update(self, site_key: str, status: str, message: str) -> bool:
        """
        상태 업데이트 WebSocket 브로드캐스트

        Args:
            site_key: 사이트 식별자
            status: 상태 코드
            message: 상태 메시지

        Returns:
            발송 성공 여부
        """
        if not self.is_enabled:
            return True

        try:
            site_name = self._get_site_name(site_key)

            ws_message = {
                "type": "status",
                "site_key": site_key,
                "site_name": site_name,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }

            await self._manager.broadcast(ws_message)
            return True

        except Exception as e:
            self._logger.error(f"WebSocket 상태 업데이트 실패: {e}")
            return False

    async def send_progress_update(
        self,
        site_key: str,
        progress: int,
        message: str = ""
    ) -> bool:
        """
        진행률 업데이트 WebSocket 브로드캐스트

        Args:
            site_key: 사이트 식별자
            progress: 진행률 (0-100)
            message: 상태 메시지

        Returns:
            발송 성공 여부
        """
        if not self.is_enabled:
            return True

        try:
            site_name = self._get_site_name(site_key)

            ws_message = {
                "type": "progress",
                "site_key": site_key,
                "site_name": site_name,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }

            await self._manager.broadcast(ws_message)
            return True

        except Exception as e:
            self._logger.error(f"WebSocket 진행률 업데이트 실패: {e}")
            return False

    def _get_site_name(self, site_key: str) -> str:
        """사이트 키로 표시명 조회"""
        try:
            return SITE_DISPLAY[site_key].name
        except KeyError:
            return site_key
