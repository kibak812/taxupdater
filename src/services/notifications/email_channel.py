"""
이메일 알림 채널 (Strategy 패턴)

GPT-5.2 권장사항 반영:
- 기존 notification_service.py에서 이메일 관련 로직만 분리
- INotificationChannel 인터페이스 구현
- 단일 책임: 이메일 발송만 담당

크기: 기존 ~400줄 → ~150줄
"""

import os
import smtplib
import asyncio
import inspect
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from src.core.ports.notification_port import INotificationChannel
from src.core.domain.crawl_result import CrawlResult
from src.config.sites import SITE_DISPLAY
from src.config.logging_config import get_logger


@dataclass
class EmailConfig:
    """이메일 설정"""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    email_address: str
    use_tls: bool = True
    min_data_threshold: int = 1


class EmailChannel(INotificationChannel):
    """
    이메일 알림 채널

    SMTP를 통해 이메일 알림을 발송합니다.
    ThreadPoolExecutor를 사용하여 비동기로 발송.

    자원 관리:
        채널 사용 완료 후 반드시 shutdown()을 호출하거나
        context manager로 사용하세요.

    사용 예:
        # 방법 1: 명시적 shutdown
        channel = EmailChannel(get_email_settings=get_active_email_settings)
        try:
            await channel.send_new_data_notification(result)
        finally:
            channel.shutdown()

        # 방법 2: context manager
        with EmailChannel(get_email_settings=get_active_email_settings) as channel:
            await channel.send_new_data_notification(result)
    """

    def __init__(
        self,
        get_email_settings: Optional[callable] = None,
        enabled: bool = True,
        max_workers: int = 3
    ):
        """
        이메일 채널 초기화

        Args:
            get_email_settings: 활성 이메일 설정 조회 함수 (async)
            enabled: 채널 활성화 여부
            max_workers: ThreadPoolExecutor 워커 수
        """
        self._enabled = enabled
        self._get_email_settings = get_email_settings
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._logger = get_logger(__name__)
        self._shutdown = False

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료 - 자원 정리"""
        self.shutdown()
        return False

    def shutdown(self, wait: bool = True):
        """
        ThreadPoolExecutor 정리

        Args:
            wait: 실행 중인 작업 완료 대기 여부

        Note:
            Martin Fowler 리팩토링 원칙 적용:
            자원 누수 방지를 위해 명시적 정리 메서드 제공
        """
        if not self._shutdown:
            self._executor.shutdown(wait=wait)
            self._shutdown = True
            self._logger.debug("EmailChannel executor shutdown completed")

    def __del__(self):
        """소멸자 - 안전망으로 자원 정리 시도"""
        try:
            if hasattr(self, '_shutdown') and not self._shutdown:
                self.shutdown(wait=False)
        except Exception:
            pass  # 소멸자에서는 예외 무시

    @property
    def channel_name(self) -> str:
        return "email"

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        """채널 활성화/비활성화"""
        self._enabled = enabled

    async def send_new_data_notification(self, result: CrawlResult) -> bool:
        """
        새 데이터 발견 이메일 알림 발송

        Args:
            result: 크롤링 결과

        Returns:
            발송 성공 여부
        """
        if not self._enabled:
            return True

        if not result.has_new_data:
            return True

        try:
            # 이메일 설정 조회
            settings = await self._get_email_settings_safe()
            if not settings:
                self._logger.debug("활성화된 이메일 설정 없음")
                return True

            # 이메일 내용 생성
            site_name = self._get_site_name(result.site_key)
            subject = f"[예규판례 모니터링] 새로운 데이터 발견: {site_name}"
            html_content = self._create_html_content(result, site_name)

            # 각 수신자에게 발송
            success_count = 0
            for setting in settings:
                if result.statistics.new_count < setting.get('min_data_threshold', 1):
                    continue

                if await self._send_email(setting, subject, html_content):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            self._logger.error(f"이메일 알림 발송 실패: {e}")
            return False

    async def send_error_notification(self, result: CrawlResult) -> bool:
        """
        에러 알림 이메일 발송

        Args:
            result: 에러가 발생한 크롤링 결과

        Returns:
            발송 성공 여부
        """
        if not self._enabled:
            return True

        try:
            settings = await self._get_email_settings_safe()
            if not settings:
                return True

            site_name = self._get_site_name(result.site_key)
            subject = f"[예규판례 모니터링] 크롤링 오류: {site_name}"
            html_content = self._create_error_html(result, site_name)

            success_count = 0
            for setting in settings:
                if await self._send_email(setting, subject, html_content):
                    success_count += 1

            return success_count > 0

        except Exception as e:
            self._logger.error(f"에러 알림 이메일 발송 실패: {e}")
            return False

    async def _get_email_settings_safe(self) -> List[Dict[str, Any]]:
        """이메일 설정 안전하게 조회"""
        if not self._get_email_settings:
            return []

        try:
            if inspect.iscoroutinefunction(self._get_email_settings):
                return await self._get_email_settings()
            else:
                return self._get_email_settings()
        except Exception as e:
            self._logger.error(f"이메일 설정 조회 실패: {e}")
            return []

    async def _send_email(self, setting: Dict[str, Any], subject: str, html_content: str) -> bool:
        """비동기 이메일 발송"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._send_email_sync,
            setting,
            subject,
            html_content
        )

    def _send_email_sync(
        self,
        setting: Dict[str, Any],
        subject: str,
        html_content: str,
        max_retries: int = 3
    ) -> bool:
        """동기 이메일 발송 (재시도 로직 포함)"""
        email_password = os.getenv('EMAIL_PASSWORD')
        if not email_password:
            self._logger.error("EMAIL_PASSWORD 환경 변수가 설정되지 않음")
            return False

        for attempt in range(max_retries):
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = setting.get('smtp_username') or setting.get('email_address')
                msg['To'] = setting.get('email_address')

                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)

                with smtplib.SMTP(setting['smtp_server'], int(setting['smtp_port'])) as server:
                    if setting.get('use_tls', True):
                        server.starttls()
                    server.login(
                        setting.get('smtp_username') or setting.get('email_address'),
                        email_password
                    )
                    server.send_message(msg)

                self._logger.info(f"이메일 발송 성공: {setting.get('email_address')}")
                return True

            except Exception as e:
                self._logger.warning(f"이메일 발송 시도 {attempt + 1}/{max_retries} 실패: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)

        self._logger.error(f"이메일 발송 최종 실패: {setting.get('email_address')}")
        return False

    def _get_site_name(self, site_key: str) -> str:
        """사이트 키로 표시명 조회"""
        try:
            return SITE_DISPLAY[site_key].name
        except KeyError:
            return site_key

    def _create_html_content(self, result: CrawlResult, site_name: str) -> str:
        """새 데이터 알림 HTML 생성"""
        dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8001')

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Inter', -apple-system, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f3f4f6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
                .header h2 {{ margin: 0; color: #1f2937; }}
                .content {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 16px; }}
                .stat {{ text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #3b82f6; }}
                .stat-label {{ font-size: 14px; color: #6b7280; }}
                .button {{ display: inline-block; background: #3b82f6; color: white; padding: 10px 20px;
                          border-radius: 6px; text-decoration: none; margin-top: 16px; }}
                .footer {{ margin-top: 20px; text-align: center; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>새로운 데이터 발견: {site_name}</h2>
                    <p style="margin: 8px 0 0 0; color: #6b7280;">
                        {result.statistics.new_count}개의 새로운 데이터가 발견되었습니다.
                    </p>
                </div>

                <div class="content">
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{result.statistics.new_count}</div>
                            <div class="stat-label">신규</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{result.statistics.total_crawled}</div>
                            <div class="stat-label">크롤링</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{result.statistics.existing_count}</div>
                            <div class="stat-label">기존</div>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <a href="{dashboard_url}/data/{result.site_key}" class="button">
                            전체 데이터 보기
                        </a>
                    </div>
                </div>

                <div class="footer">
                    <p>이 이메일은 예규판례 모니터링 시스템에서 자동으로 발송되었습니다.</p>
                    <p><a href="{dashboard_url}/settings" style="color: #3b82f6;">알림 설정 변경</a></p>
                </div>
            </div>
        </body>
        </html>
        """

    def _create_error_html(self, result: CrawlResult, site_name: str) -> str:
        """에러 알림 HTML 생성"""
        dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8001')

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Inter', -apple-system, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #fee2e2; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
                .header h2 {{ margin: 0; color: #dc2626; }}
                .content {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
                .error-message {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px;
                                padding: 12px; color: #dc2626; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>크롤링 오류: {site_name}</h2>
                </div>

                <div class="content">
                    <p>크롤링 중 오류가 발생했습니다:</p>
                    <div class="error-message">
                        {result.error_message or "알 수 없는 오류"}
                    </div>
                    <p style="margin-top: 16px; color: #6b7280;">
                        발생 시간: {result.crawled_at.strftime("%Y-%m-%d %H:%M:%S")}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
