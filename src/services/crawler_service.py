import sys
import os
from tkinter import messagebox
from typing import Dict, Any

# 상위 디렉토리 모듈 import를 위한 경로 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import CrawlerInterface, DataRepositoryInterface


class CrawlingService:
    """
    크롤링 오케스트레이션 서비스
    
    클래스 기반 크롤러와 Repository 패턴을 사용하여
    향후 DB 및 웹 전환을 대비한 확장 가능한 구조
    """
    
    def __init__(self, crawlers: Dict[str, CrawlerInterface], repository: DataRepositoryInterface):
        """
        크롤링 서비스 초기화
        
        Args:
            crawlers: 사이트별 크롤러 인스턴스 딕셔너리
            repository: 데이터 저장소 인스턴스
        """
        self.crawlers = crawlers
        self.repository = repository
    
    def execute_crawling(self, choice: str, progress, status_message, is_periodic: bool = False):
        """
        통합 크롤링 실행 로직 (클래스 기반)
        
        Args:
            choice: 사용자 선택 ("1"-"7")
            progress: 진행률 콜백
            status_message: 상태 메시지 콜백
            is_periodic: 주기적 실행 여부
        """
        summary_messages = []
        prefix = "주기적 크롤링 " if is_periodic else ""
        
        # 선택에 따른 크롤러 매핑
        crawler_mapping = {
            "1": ["tax_tribunal"],
            "2": ["nts_authority"],
            "3": ["moef"],
            "4": ["nts_precedent"],
            "5": ["mois"],
            "6": ["bai"],
            "7": ["tax_tribunal", "nts_authority", "moef", "nts_precedent", "mois", "bai"]
        }
        
        selected_crawlers = crawler_mapping.get(choice, [])
        
        if not selected_crawlers:
            self._show_message("잘못된 선택입니다. 유효한 옵션을 선택해 주세요.")
            return
        
        # 선택된 크롤러들 실행
        for crawler_key in selected_crawlers:
            if crawler_key in self.crawlers:
                msg = self._execute_single_crawler(crawler_key, progress, status_message, prefix)
                if choice == "7":
                    summary_messages.append(msg)
                else:
                    self._show_message(msg)
            else:
                error_msg = f"{prefix}크롤러 '{crawler_key}'를 찾을 수 없습니다."
                if choice == "7":
                    summary_messages.append(error_msg)
                else:
                    self._show_message(error_msg)
        
        # 전체 크롤링 결과 표시
        if choice == "7" and summary_messages:
            result_prefix = "주기적 크롤링 결과:\n" if is_periodic else ""
            self._show_message(result_prefix + "\n".join(summary_messages))
        elif choice == "7":
            self._show_message(f"{prefix}: 처리된 항목이 없습니다.")
    
    def _execute_single_crawler(self, crawler_key: str, progress, status_message, prefix: str) -> str:
        """
        단일 크롤러 실행
        
        Args:
            crawler_key: 크롤러 키
            progress: 진행률 콜백
            status_message: 상태 메시지 콜백
            prefix: 메시지 접두사
            
        Returns:
            실행 결과 메시지
        """
        try:
            crawler = self.crawlers[crawler_key]
            site_name = crawler.get_site_name()
            
            # 크롤링 실행
            new_data = crawler.crawl(progress_callback=progress, status_callback=status_message)
            
            # 데이터 유효성 검증
            if not crawler.validate_data(new_data):
                return f"{prefix}({site_name}): 크롤링된 데이터가 유효하지 않습니다."
            
            if new_data.empty:
                return f"{prefix}({site_name}): 크롤링 결과 데이터 없음."
            
            # 신규 데이터 확인
            key_column = crawler.get_key_column()
            new_entries = self.repository.compare_and_get_new_entries(
                crawler_key, new_data, key_column
            )
            
            if not new_entries.empty:
                # 백업 생성
                self.repository.backup_data(crawler_key, new_entries)
                
                # 데이터 저장
                self.repository.save_data(crawler_key, new_data, is_incremental=True)
                
                return f"{prefix}({site_name}): 새로운 데이터 {len(new_entries)}개 발견."
            else:
                return f"{prefix}({site_name}): 새로운 데이터 없음."
                
        except Exception as e:
            return f"{prefix}({crawler_key}): 오류 발생 - {str(e)}"
    
    def get_crawler_statistics(self) -> Dict[str, Any]:
        """모든 크롤러의 통계 정보 반환"""
        stats = {}
        for crawler_key, crawler in self.crawlers.items():
            try:
                site_name = crawler.get_site_name()
                repo_stats = self.repository.get_statistics(crawler_key)
                stats[site_name] = repo_stats
            except Exception as e:
                stats[crawler_key] = {"error": str(e)}
        return stats
    
    def _show_message(self, message):
        """메시지 표시"""
        messagebox.showinfo("크롤링 완료", message)