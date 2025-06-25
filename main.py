"""
Tax Law Crawler - 리팩토링된 메인 진입점

사용법:
    python main.py
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(__file__))

from src.gui.main_window import MainWindow
from src.services.crawler_service import CrawlingService
from src.services.data_service import DataService

# 기존 크롤러 함수들을 import (example.py에서)
# TODO: 이후 단계에서 이 함수들도 클래스로 분리 예정
from example import (
    crawl_data, crawl_dynamic_site, crawl_nts_precedents,
    crawl_moef_site, crawl_mois_site, crawl_bai_site
)


def main():
    """메인 함수"""
    try:
        # 서비스 초기화
        data_service = DataService()
        
        # 크롤러 함수들을 딕셔너리로 구성
        crawler_functions = {
            'crawl_data': crawl_data,
            'crawl_dynamic_site': crawl_dynamic_site,
            'crawl_nts_precedents': crawl_nts_precedents,
            'crawl_moef_site': crawl_moef_site,
            'crawl_mois_site': crawl_mois_site,
            'crawl_bai_site': crawl_bai_site
        }
        
        # 크롤링 서비스 초기화
        crawling_service = CrawlingService(crawler_functions, data_service)
        
        # GUI 초기화 및 실행
        app = MainWindow(crawling_service)
        app.run()
        
    except Exception as e:
        print(f"애플리케이션 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()