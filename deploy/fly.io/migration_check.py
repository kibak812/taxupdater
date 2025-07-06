#!/usr/bin/env python3
"""
Fly.io 배포용 마이그레이션 확인 및 실행 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.database.migrations import DatabaseMigration
from src.repositories.sqlite_repository import SQLiteRepository
from src.config.logging_config import setup_logging, get_logger

def main():
    """메인 실행 함수"""
    # 로깅 설정
    setup_logging(log_level="INFO")
    logger = get_logger(__name__)
    
    logger.info("=== Fly.io 배포용 마이그레이션 확인 시작 ===")
    
    try:
        # 데이터베이스 경로 확인
        repository = SQLiteRepository()
        db_path = repository.db_path
        logger.info(f"데이터베이스 경로: {db_path}")
        
        # 마이그레이션 객체 생성
        migration = DatabaseMigration(db_path)
        
        # 마이그레이션 상태 확인
        logger.info("마이그레이션 상태 확인 중...")
        status = migration.get_migration_status()
        
        logger.info(f"마이그레이션 필요: {status['migration_needed']}")
        logger.info(f"기존 테이블: {len(status['existing_tables'])}개")
        logger.info(f"누락 테이블: {len(status['missing_tables'])}개")
        
        if status['missing_tables']:
            logger.warning(f"누락된 테이블들: {', '.join(status['missing_tables'])}")
        
        # 마이그레이션 실행
        if status['migration_needed']:
            logger.info("마이그레이션 실행 중...")
            migration.migrate_to_monitoring_system()
            logger.info("✅ 마이그레이션 완료!")
        else:
            logger.info("✅ 마이그레이션이 필요하지 않습니다")
        
        # 서비스 초기화 테스트
        logger.info("서비스 초기화 테스트 중...")
        
        from src.services.crawler_service import CrawlingService
        from src.services.scheduler_service import SchedulerService
        from src.services.notification_service import NotificationService
        from src.crawlers.tax_tribunal_crawler import TaxTribunalCrawler
        from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler
        from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler
        
        # 크롤러 초기화
        crawlers = {
            "tax_tribunal": TaxTribunalCrawler(),
            "nts_authority": NTSAuthorityCrawler(),
            "nts_precedent": NTSPrecedentCrawler(),
        }
        
        crawling_service = CrawlingService(crawlers, repository)
        logger.info("✅ CrawlingService 초기화 성공")
        
        # 스케줄러 서비스 초기화
        scheduler_service = SchedulerService(db_path=db_path, crawling_service=crawling_service)
        logger.info("✅ SchedulerService 초기화 성공")
        
        # 알림 서비스 초기화
        notification_service = NotificationService(db_path=db_path)
        logger.info("✅ NotificationService 초기화 성공")
        
        logger.info("=== 모든 확인 완료! 시스템이 정상적으로 작동할 준비가 되었습니다 ===")
        return True
        
    except Exception as e:
        logger.error(f"❌ 마이그레이션 확인 실패: {e}")
        import traceback
        logger.error(f"상세 오류:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)