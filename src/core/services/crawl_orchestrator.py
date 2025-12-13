"""
크롤링 오케스트레이터

GPT-5.2 권장사항 반영:
- Observer 패턴 대신 단일 NotificationDispatcher 포트 사용
- 크롤러, 저장소, 알림을 조율하는 단일 진입점
- 새 데이터 탐지 및 저장 로직 캡슐화
- asyncio.to_thread로 블로킹 호출 분리 (Codex 리뷰 반영)

크기: ~120줄
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
import pandas as pd

from src.core.ports.crawler_port import ICrawler
from src.core.ports.repository_port import IRepository
from src.core.ports.notification_port import INotificationDispatcher
from src.core.domain.crawl_result import CrawlResult, CrawlStatistics, CrawlStatus
from src.config.logging_config import get_logger


class CrawlOrchestrator:
    """
    크롤링 오케스트레이션

    GPT-5.2 권장: Observer 패턴 대신 단일 NotificationDispatcher 포트로 구현.
    크롤러 실행 → 새 데이터 탐지 → 저장 → 알림의 전체 흐름을 조율합니다.

    사용 예:
        orchestrator = CrawlOrchestrator(
            crawlers={"tax_tribunal": TaxTribunalCrawler()},
            repository=sqlite_repository,
            notification_dispatcher=dispatcher
        )
        result = await orchestrator.execute_crawl("tax_tribunal", max_items=100)
    """

    def __init__(
        self,
        crawlers: Dict[str, ICrawler],
        repository: IRepository,
        notification_dispatcher: INotificationDispatcher
    ):
        """
        오케스트레이터 초기화

        Args:
            crawlers: site_key -> ICrawler 매핑
            repository: 데이터 저장소
            notification_dispatcher: 알림 디스패처
        """
        self._crawlers = crawlers
        self._repository = repository
        self._notifier = notification_dispatcher
        self._logger = get_logger(__name__)

    def get_available_sites(self) -> List[str]:
        """사용 가능한 사이트 목록"""
        return list(self._crawlers.keys())

    async def execute_crawl(
        self,
        site_key: str,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        **kwargs
    ) -> CrawlResult:
        """
        크롤링 실행

        Args:
            site_key: 크롤링할 사이트 키
            progress_callback: 진행률 콜백 (0-100)
            status_callback: 상태 메시지 콜백
            **kwargs: 크롤러에 전달할 추가 인자

        Returns:
            CrawlResult: 크롤링 결과

        Raises:
            KeyError: 알 수 없는 사이트 키
        """
        if site_key not in self._crawlers:
            raise KeyError(f"Unknown site: {site_key}")

        crawler = self._crawlers[site_key]
        start_time = datetime.now()

        try:
            # 1. 크롤링 실행 (블로킹 → 별도 스레드)
            if status_callback:
                status_callback(f"크롤링 시작: {site_key}")

            crawled_data = await asyncio.to_thread(
                crawler.crawl,
                progress_callback=progress_callback,
                status_callback=status_callback,
                **kwargs
            )

            # 2. 기존 데이터 로드 (블로킹 → 별도 스레드)
            existing_data = await asyncio.to_thread(
                self._repository.load_existing_data,
                site_key
            )

            # 3. 새 데이터 탐지
            key_column = crawler.get_key_column()
            new_entries = self._detect_new_entries(
                crawled_data, existing_data, key_column
            )

            # 4. 새 데이터 저장 (블로킹 → 별도 스레드)
            if not new_entries.empty:
                await asyncio.to_thread(
                    self._repository.save_data,
                    site_key,
                    new_entries
                )

            # 5. 결과 생성
            duration = (datetime.now() - start_time).total_seconds()
            result = CrawlResult.success(
                site_key=site_key,
                statistics=CrawlStatistics(
                    total_crawled=len(crawled_data),
                    new_count=len(new_entries),
                    existing_count=len(existing_data),
                    duplicate_count=len(crawled_data) - len(new_entries),
                    duration_seconds=duration
                ),
                new_entries=new_entries if not new_entries.empty else None
            )

            # 6. 새 데이터 알림 (있을 경우만)
            if result.has_new_data:
                await self._notifier.dispatch_new_data(result)
                self._logger.info(
                    f"[{site_key}] 새 데이터 {result.statistics.new_count}건 발견"
                )

            return result

        except Exception as e:
            # 에러 결과 생성
            duration = (datetime.now() - start_time).total_seconds()
            result = CrawlResult.error(
                site_key=site_key,
                error_message=str(e)
            )

            # 에러 알림
            await self._notifier.dispatch_error(result)
            self._logger.error(f"[{site_key}] 크롤링 에러: {e}")

            return result

    def _detect_new_entries(
        self,
        crawled: pd.DataFrame,
        existing: pd.DataFrame,
        key_column: str
    ) -> pd.DataFrame:
        """
        새 데이터 탐지 (중복 제거)

        Args:
            crawled: 크롤링된 데이터
            existing: 기존 데이터
            key_column: 키 컬럼명

        Returns:
            새로운 데이터만 포함된 DataFrame
        """
        if crawled.empty:
            return pd.DataFrame()

        if existing.empty or key_column not in existing.columns:
            return crawled

        if key_column not in crawled.columns:
            self._logger.warning(f"키 컬럼 '{key_column}'이 크롤링 데이터에 없음")
            return crawled

        # 기존 키 세트
        existing_keys = set(existing[key_column].astype(str))

        # 새 데이터 필터링
        mask = ~crawled[key_column].astype(str).isin(existing_keys)
        return crawled[mask].copy()
