"""
알림 디스패처 (단일 포트)

GPT-5.2 권장사항 반영:
- Observer 패턴 대신 단일 Dispatcher 포트 사용
- 모든 알림 채널을 조율
- INotificationDispatcher 인터페이스 구현

크기: ~100줄
"""

from typing import List, Dict

from src.core.ports.notification_port import INotificationChannel, INotificationDispatcher
from src.core.domain.crawl_result import CrawlResult
from src.config.logging_config import get_logger


class NotificationDispatcher(INotificationDispatcher):
    """
    알림 발송 조율자

    GPT-5.2 권장: Observer 패턴 대신 단일 Dispatcher 포트로 구현.
    모든 알림 채널을 조율하여 새 데이터, 에러, 상태 알림을 발송합니다.

    사용 예:
        email_channel = EmailChannel(...)
        ws_channel = WebSocketChannel(...)
        dispatcher = NotificationDispatcher([email_channel, ws_channel])

        await dispatcher.dispatch_new_data(crawl_result)
    """

    def __init__(self, channels: List[INotificationChannel] = None):
        """
        디스패처 초기화

        Args:
            channels: 알림 채널 목록
        """
        self._channels = channels or []
        self._logger = get_logger(__name__)

    def add_channel(self, channel: INotificationChannel):
        """채널 추가"""
        self._channels.append(channel)

    def remove_channel(self, channel_name: str) -> bool:
        """채널 제거"""
        for i, channel in enumerate(self._channels):
            if channel.channel_name == channel_name:
                self._channels.pop(i)
                return True
        return False

    @property
    def active_channels(self) -> List[str]:
        """현재 활성화된 채널 목록"""
        return [ch.channel_name for ch in self._channels if ch.is_enabled]

    async def dispatch_new_data(self, result: CrawlResult) -> Dict[str, bool]:
        """
        새 데이터 알림을 모든 활성 채널로 발송

        Args:
            result: 새 데이터가 포함된 크롤링 결과

        Returns:
            채널별 발송 결과 {"email": True, "websocket": True, ...}
        """
        if not result.has_new_data:
            return {}

        results = {}
        for channel in self._channels:
            if channel.is_enabled:
                try:
                    success = await channel.send_new_data_notification(result)
                    results[channel.channel_name] = success
                    if success:
                        self._logger.info(
                            f"[{channel.channel_name}] 새 데이터 알림 발송 성공: {result.site_key}"
                        )
                    else:
                        self._logger.warning(
                            f"[{channel.channel_name}] 새 데이터 알림 발송 실패: {result.site_key}"
                        )
                except Exception as e:
                    results[channel.channel_name] = False
                    self._logger.error(
                        f"[{channel.channel_name}] 새 데이터 알림 발송 에러: {e}"
                    )

        return results

    async def dispatch_error(self, result: CrawlResult) -> Dict[str, bool]:
        """
        에러 알림을 모든 활성 채널로 발송

        Args:
            result: 에러가 발생한 크롤링 결과

        Returns:
            채널별 발송 결과
        """
        results = {}
        for channel in self._channels:
            if channel.is_enabled:
                try:
                    success = await channel.send_error_notification(result)
                    results[channel.channel_name] = success
                    if success:
                        self._logger.info(
                            f"[{channel.channel_name}] 에러 알림 발송 성공: {result.site_key}"
                        )
                except Exception as e:
                    results[channel.channel_name] = False
                    self._logger.error(
                        f"[{channel.channel_name}] 에러 알림 발송 에러: {e}"
                    )

        return results

    async def dispatch_status(
        self,
        site_key: str,
        status: str,
        message: str
    ) -> Dict[str, bool]:
        """
        상태 업데이트를 모든 활성 채널로 발송

        Args:
            site_key: 사이트 식별자
            status: 상태 코드
            message: 상태 메시지

        Returns:
            채널별 발송 결과
        """
        results = {}
        for channel in self._channels:
            if channel.is_enabled:
                try:
                    success = await channel.send_status_update(site_key, status, message)
                    results[channel.channel_name] = success
                except Exception as e:
                    results[channel.channel_name] = False
                    self._logger.debug(
                        f"[{channel.channel_name}] 상태 업데이트 발송 에러: {e}"
                    )

        return results
