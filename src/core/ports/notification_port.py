"""
알림 포트 인터페이스

Hexagonal Architecture의 포트 정의:
- INotificationChannel: 개별 알림 채널 인터페이스 (Strategy 패턴)
- INotificationDispatcher: 알림 발송 조율자 인터페이스

GPT-5.2 권장사항:
- Observer 패턴 대신 단일 Dispatcher 포트 사용
- 채널별 Strategy 패턴으로 확장성 확보
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from src.core.domain.crawl_result import CrawlResult


class INotificationChannel(ABC):
    """
    알림 채널 인터페이스 (Strategy 패턴)

    구현체 예시:
    - EmailChannel: 이메일 발송
    - WebSocketChannel: 실시간 WebSocket 브로드캐스트
    - SlackChannel: Slack 웹훅 (미래 확장)

    사용 예:
        channel: INotificationChannel = EmailChannel(smtp_config)
        await channel.send_new_data_notification(result)
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """채널 식별자 (예: "email", "websocket")"""
        pass

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        """채널 활성화 상태"""
        pass

    @abstractmethod
    async def send_new_data_notification(self, result: CrawlResult) -> bool:
        """
        새 데이터 발견 알림 발송

        Args:
            result: 크롤링 결과 (새 데이터 포함)

        Returns:
            발송 성공 여부
        """
        pass

    @abstractmethod
    async def send_error_notification(self, result: CrawlResult) -> bool:
        """
        크롤링 에러 알림 발송

        Args:
            result: 에러가 발생한 크롤링 결과

        Returns:
            발송 성공 여부
        """
        pass

    async def send_status_update(self, site_key: str, status: str, message: str) -> bool:
        """
        상태 업데이트 알림 (선택적 구현)

        기본 구현: 아무것도 하지 않음 (WebSocket 채널에서 오버라이드)

        Args:
            site_key: 사이트 식별자
            status: 상태 코드
            message: 상태 메시지

        Returns:
            발송 성공 여부
        """
        return True


class INotificationDispatcher(ABC):
    """
    알림 발송 조율자 인터페이스 (Port)

    GPT-5.2 권장: Observer 패턴 대신 단일 Dispatcher 포트 사용
    - 모든 알림 채널을 조율
    - 채널별 활성화 상태에 따라 선택적 발송

    사용 예:
        dispatcher = NotificationDispatcher([email_channel, ws_channel])
        await dispatcher.dispatch_new_data(result)
    """

    @abstractmethod
    async def dispatch_new_data(self, result: CrawlResult) -> dict:
        """
        새 데이터 알림을 모든 활성 채널로 발송

        Args:
            result: 새 데이터가 포함된 크롤링 결과

        Returns:
            채널별 발송 결과 {"email": True, "websocket": True, ...}
        """
        pass

    @abstractmethod
    async def dispatch_error(self, result: CrawlResult) -> dict:
        """
        에러 알림을 모든 활성 채널로 발송

        Args:
            result: 에러가 발생한 크롤링 결과

        Returns:
            채널별 발송 결과
        """
        pass

    @abstractmethod
    async def dispatch_status(self, site_key: str, status: str, message: str) -> dict:
        """
        상태 업데이트를 모든 활성 채널로 발송

        Args:
            site_key: 사이트 식별자
            status: 상태 코드
            message: 상태 메시지

        Returns:
            채널별 발송 결과
        """
        pass

    @property
    @abstractmethod
    def active_channels(self) -> List[str]:
        """현재 활성화된 채널 목록"""
        pass
