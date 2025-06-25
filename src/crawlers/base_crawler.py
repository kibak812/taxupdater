import sys
import os
import pandas as pd
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.interfaces.crawler_interface import CrawlerInterface
from src.config.settings import SELENIUM_OPTIONS, CRAWLING_CONFIG


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
    
    def safe_selenium_operation(self, operation_func, retries: int = None, delay: int = None):
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
                print(f"Selenium 작업 시도 {attempt + 1} 실패: {e}")
                if attempt < retries - 1:
                    print(f"{delay}초 후 재시도...")
                    import time
                    time.sleep(delay)
                else:
                    print("최대 재시도 횟수 도달. 작업 실패.")
                    raise e
    
    def update_progress_safely(self, progress_callback, value: int, message: str = ""):
        """안전한 진행률 업데이트"""
        try:
            if progress_callback and hasattr(progress_callback, '__call__'):
                progress_callback(value, message)
            elif progress_callback and hasattr(progress_callback, 'value'):
                # tkinter Progressbar 객체인 경우
                progress_callback['value'] = value
                if hasattr(progress_callback, 'update'):
                    progress_callback.update()
        except Exception as e:
            print(f"진행률 업데이트 중 오류: {e}")
    
    def update_status_safely(self, status_callback, message: str):
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
            print(f"상태 메시지 업데이트 중 오류: {e}")
    
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
                print(f"{self.site_name}: 중복 {removed_count}개 제거")
        
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
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            "max_pages": self.config.get("max_pages", 10),
            "max_items": self.config.get("max_items", 1000),
            "timeout": self.config.get("timeout", 10),
            "retry_count": self.config.get("retry_count", 3),
            "retry_delay": self.config.get("retry_delay", 5)
        }