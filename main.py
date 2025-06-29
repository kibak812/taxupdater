"""
Tax Law Crawler - 리팩토링된 메인 진입점 (클래스 기반)

사용법:
    python main.py
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(__file__))

# 로깅 시스템 초기화
from src.config.logging_config import setup_logging, get_logger
setup_logging(log_level="INFO", log_to_file=True)
logger = get_logger(__name__)

from src.gui.main_window import MainWindow
from src.services.crawler_service import CrawlingService
from src.repositories.sqlite_repository import SQLiteRepository

# 클래스 기반 크롤러들 import
from src.crawlers.tax_tribunal_crawler import TaxTribunalCrawler
from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler
from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler

# 레거시 크롤러 함수들 (아직 클래스로 변환되지 않은 것들)
from example import (
    crawl_moef_site, crawl_mois_site, crawl_bai_site
)

# 임시 래퍼 클래스들 (향후 완전한 클래스로 대체 예정)
class LegacyCrawlerWrapper:
    """레거시 크롤러 함수를 클래스 인터페이스로 래핑"""
    def __init__(self, site_name, site_key, crawler_func, key_column):
        self.site_name = site_name
        self.site_key = site_key
        self.crawler_func = crawler_func
        self.key_column = key_column
    
    def get_site_name(self):
        return self.site_name
    
    def get_site_key(self):
        return self.site_key
    
    def get_key_column(self):
        return self.key_column
    
    def crawl(self, progress_callback=None, status_callback=None, **kwargs):
        return self.crawler_func(progress=progress_callback, status_message=status_callback, **kwargs)
    
    def validate_data(self, data):
        return not data.empty if data is not None else False


def main():
    """메인 함수"""
    try:
        # Repository 초기화 (SQLite 기반 고성능 데이터 저장소)
        repository = SQLiteRepository()
        
        # 크롤러 인스턴스 생성
        crawlers = {
            "tax_tribunal": TaxTribunalCrawler(),
            "nts_authority": NTSAuthorityCrawler(),
            "nts_precedent": NTSPrecedentCrawler(),
            # 레거시 크롤러들을 래퍼로 감싸서 사용
            "moef": LegacyCrawlerWrapper(
                "기획재정부", "moef", crawl_moef_site, "문서번호"
            ),
            "mois": LegacyCrawlerWrapper(
                "행정안전부", "mois", crawl_mois_site, "문서번호"
            ),
            "bai": LegacyCrawlerWrapper(
                "감사원", "bai", crawl_bai_site, "문서번호"
            )
        }
        
        # 크롤링 서비스 초기화
        crawling_service = CrawlingService(crawlers, repository)
        
        # GUI 초기화 및 실행
        app = MainWindow(crawling_service)
        app.run()
        
    except Exception as e:
        print(f"애플리케이션 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()