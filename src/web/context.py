"""
FastAPI application context and default dependency wiring.

The web layer historically kept repository, crawler, scheduler, notification,
template, and websocket objects as module globals in ``app.py``.  This module
keeps the same default wiring, but packages it in a small context object so
routes can be tested with fakes.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import WebSocket


PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.sites import get_legacy_site_info


def get_configured_ngrok_url() -> str:
    """Return the configured static ngrok URL, if one is available."""
    configured_url = os.environ.get("NGROK_URL", "").strip()
    if configured_url:
        return configured_url

    if sys.platform == "darwin":
        try:
            import subprocess

            result = subprocess.run(
                ["launchctl", "getenv", "NGROK_URL"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            configured_url = result.stdout.strip()
            if configured_url:
                return configured_url
        except Exception:
            pass

    return ""


class ConnectionManager:
    """Manage active crawl WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass


@dataclass
class WebAppContext:
    project_root: Path
    repository: Any
    crawlers: Dict[str, Any]
    crawling_service: Any
    manager: ConnectionManager
    scheduler_service: Optional[Any]
    notification_service: Optional[Any]
    site_info: Dict[str, Dict[str, str]]
    logger: Any
    templates: Optional[Any] = None


def _load_crawlers(logger) -> Dict[str, Any]:
    from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler
    from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler
    from src.crawlers.scourt_major_decision_crawler import ScourtMajorDecisionCrawler
    from src.crawlers.scourt_scheduled_decision_crawler import ScourtScheduledDecisionCrawler
    from src.crawlers.tax_tribunal_crawler import TaxTribunalCrawler

    crawlers = {
        "tax_tribunal": TaxTribunalCrawler(),
        "nts_authority": NTSAuthorityCrawler(),
        "nts_precedent": NTSPrecedentCrawler(),
        "scourt_major_decisions": ScourtMajorDecisionCrawler(),
        "scourt_scheduled_decisions": ScourtScheduledDecisionCrawler(),
    }

    try:
        from src.crawlers.web_legacy_crawlers import (
            crawl_bai_site,
            crawl_moef_site,
            crawl_mois_site,
        )

        # Keep these names referenced so import availability mirrors the old app.
        _ = (crawl_moef_site, crawl_mois_site, crawl_bai_site)
        from src.crawlers.legacy_adapter import (
            create_bai_adapter,
            create_moef_adapter,
            create_mois_adapter,
        )

        crawlers.update(
            {
                "moef": create_moef_adapter(),
                "mois": create_mois_adapter(),
                "bai": create_bai_adapter(),
            }
        )
        logger.info(f"모든 크롤러 사용 가능: {len(crawlers)}개")
    except ImportError as e:
        logger.error(f"웹 레거시 크롤러 import 실패: {e}")
        logger.warning(f"기본 크롤러만 사용 가능: {len(crawlers)}개 (레거시 크롤러 제외)")

    return crawlers


def _initialize_monitoring_services(repository, crawling_service, manager, logger):
    try:
        from src.database.migrations import DatabaseMigration
        from src.services.notification_service import NotificationService
        from src.services.scheduler_service import SchedulerService

        migration = DatabaseMigration(repository.db_path)
        migration_status = migration.get_migration_status()

        if migration_status["migration_needed"]:
            logger.warning("모니터링 시스템 테이블 누락 감지 - 자동 마이그레이션 실행")
            migration.migrate_to_monitoring_system()

        migration.ensure_default_monitoring_rows()

        scheduler_service = SchedulerService(
            db_path=repository.db_path,
            crawling_service=crawling_service,
        )
        notification_service = NotificationService(
            db_path=repository.db_path,
            websocket_manager=manager,
        )
        logger.info("모니터링 시스템 서비스 초기화 완료")
        return scheduler_service, notification_service
    except Exception as e:
        logger.error(f"모니터링 시스템 초기화 실패: {e}")
        return None, None


def create_default_context() -> WebAppContext:
    from src.config.logging_config import get_logger, setup_logging
    from src.repositories.sqlite_repository import SQLiteRepository
    from src.services.crawler_service import CrawlingService

    setup_logging(log_level="INFO", log_to_file=True)
    logger = get_logger(__name__)

    db_path = os.environ.get("DATABASE_PATH", "data/tax_data.db")
    repository = SQLiteRepository(db_path=db_path)

    logger.info("기존 데이터베이스 스키마 업데이트 중...")
    repository.force_schema_update()

    crawlers = _load_crawlers(logger)
    crawling_service = CrawlingService(crawlers, repository)
    manager = ConnectionManager()
    scheduler_service, notification_service = _initialize_monitoring_services(
        repository,
        crawling_service,
        manager,
        logger,
    )

    site_info = {key: value for key, value in get_legacy_site_info().items() if key in crawlers}

    return WebAppContext(
        project_root=PROJECT_ROOT,
        repository=repository,
        crawlers=crawlers,
        crawling_service=crawling_service,
        manager=manager,
        scheduler_service=scheduler_service,
        notification_service=notification_service,
        site_info=site_info,
        logger=logger,
    )
