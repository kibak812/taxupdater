import sys
import os
import pandas as pd
from typing import Dict, Any, Optional, Callable
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import CrawlerInterface
from src.config.settings import SELENIUM_OPTIONS, CRAWLING_CONFIG
from src.config.logging_config import get_logger


class BaseCrawler(CrawlerInterface):
    """
    기본 크롤러 클래스 - 공통 기능 제공
    
    Selenium 설정, 에러 처리, 재시도 로직 등 공통 기능을 제공하여
    개별 크롤러에서는 핵심 크롤링 로직에만 집중할 수 있도록 함
    """
    
    def __init__(self, site_name: str, site_key: str):
        self.site_name = site_name
        self.site_key = site_key
        self.config = CRAWLING_CONFIG.copy()
        self.logger = get_logger(__name__)
    
    def get_site_name(self) -> str:
        return self.site_name
    
    def get_site_key(self) -> str:
        return self.site_key
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """기본 데이터 유효성 검증"""
        if data is None or data.empty:
            return False
        
        # 필수 컬럼 체크
        key_column = self.get_key_column()
        if key_column not in data.columns:
            return False
        
        # 빈 키 값 체크
        if data[key_column].isna().any() or (data[key_column] == "").any():
            return False
        
        return True
    
    def get_selenium_driver(self) -> webdriver.Chrome:
        """Selenium 드라이버 생성"""
        options = Options()
        for option in SELENIUM_OPTIONS:
            options.add_argument(option)
        return webdriver.Chrome(options=options)
    
    def safe_selenium_operation(self, operation_func: Callable, retries: Optional[int] = None, delay: Optional[int] = None) -> Any:
        """
        안전한 Selenium 작업 실행 (재시도 로직 포함)
        
        Args:
            operation_func: 실행할 Selenium 작업 함수
            retries: 재시도 횟수
            delay: 재시도 간격 (초)
        """
        if retries is None:
            retries = self.config["retry_count"]
        if delay is None:
            delay = self.config["retry_delay"]
        
        for attempt in range(retries):
            try:
                return operation_func()
            except Exception as e:
                self.logger.warning(f"Selenium 작업 시도 {attempt + 1} 실패: {e}")
                if attempt < retries - 1:
                    self.logger.info(f"{delay}초 후 재시도...")
                    import time
                    time.sleep(delay)
                else:
                    self.logger.error("최대 재시도 횟수 도달. 작업 실패.")
                    raise e
    
    def update_progress_safely(self, progress_callback: Optional[Callable], value: int, message: str = "") -> None:
        """안전한 진행률 업데이트"""
        try:
            if progress_callback and hasattr(progress_callback, '__call__'):
                progress_callback(value, message)
            elif progress_callback and hasattr(progress_callback, 'value'):
                # WebSocketProgress 객체인 경우
                progress_callback.value = value
                if hasattr(progress_callback, 'update'):
                    progress_callback.update()
        except Exception as e:
            self.logger.error(f"진행률 업데이트 중 오류: {e}")
    
    def update_status_safely(self, status_callback: Optional[Callable], message: str) -> None:
        """안전한 상태 메시지 업데이트"""
        try:
            if status_callback and hasattr(status_callback, '__call__'):
                status_callback(message)
            elif status_callback and hasattr(status_callback, 'config'):
                # tkinter Label 객체인 경우
                status_callback.config(text=message)
                if hasattr(status_callback, 'update'):
                    status_callback.update()
        except Exception as e:
            self.logger.error(f"상태 메시지 업데이트 중 오류: {e}")
    
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """기본 데이터 전처리"""
        if data.empty:
            return data
        
        # 공통 전처리 작업
        # 1. 중복 제거 (키 컬럼 기준)
        key_column = self.get_key_column()
        if key_column in data.columns:
            original_count = len(data)
            data = data.drop_duplicates(subset=[key_column], keep='first')
            removed_count = original_count - len(data)
            if removed_count > 0:
                self.logger.info(f"{self.site_name}: 중복 {removed_count}개 제거")
        
        # 2. 빈 값 정리
        data = data.fillna("")
        
        # 3. 문자열 공백 제거
        string_columns = data.select_dtypes(include=['object']).columns
        for col in string_columns:
            data[col] = data[col].astype(str).str.strip()
        
        return data
    
    def postprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """기본 데이터 후처리"""
        if data.empty:
            return data
        
        # 데이터 정렬 (키 컬럼 기준)
        key_column = self.get_key_column()
        if key_column in data.columns:
            data = data.sort_values(by=key_column, ascending=False)
        
        # 인덱스 리셋
        data = data.reset_index(drop=True)
        
        return data
    
    def generate_links_for_new_data(self, new_data: pd.DataFrame) -> pd.DataFrame:
        """새로운 데이터에 대해 링크 생성 (기본 구현은 비어있음)"""
        # 기본적으로는 아무것도 하지 않음
        # 각 크롤러에서 필요에 따라 오버라이드
        return new_data
    
    def log_crawler_start(self) -> None:
        """크롤러 시작 로깅"""
        self.logger.info(f"[{self.site_name}] 크롤링 시작")
    
    def log_crawler_complete(self, total_items: int) -> None:
        """크롤러 완료 로깅"""
        self.logger.info(f"[{self.site_name}] 크롤링 완료 - 총 {total_items}개 항목 수집")
    
    def log_crawler_error(self, error: Exception) -> None:
        """크롤러 오류 로깅"""
        self.logger.error(f"[{self.site_name}] 크롤링 오류: {error}")
    
    def log_progress(self, current: int, total: int, message: str = "") -> None:
        """크롤링 진행률 로깅"""
        from src.config.logging_config import log_crawler_progress
        log_crawler_progress(self.site_name, current, total, message)
    
    def log_data_validation(self, is_valid: bool, item_count: int) -> None:
        """데이터 검증 결과 로깅"""
        if is_valid:
            self.logger.info(f"[{self.site_name}] 데이터 검증 성공 - {item_count}개 항목")
        else:
            self.logger.warning(f"[{self.site_name}] 데이터 검증 실패 - {item_count}개 항목")
    
    def log_selenium_action(self, action: str, details: str = "") -> None:
        """Selenium 작업 로깅"""
        message = f"[{self.site_name}] Selenium {action}"
        if details:
            message += f" - {details}"
        self.logger.debug(message)
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            "max_pages": self.config.get("max_pages", 10),
            "max_items": self.config.get("max_items", 1000),
            "timeout": self.config.get("timeout", 10),
            "retry_count": self.config.get("retry_count", 3),
            "retry_delay": self.config.get("retry_delay", 5)
        }