from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class CrawlerInterface(ABC):
    """
    크롤러 인터페이스 - 모든 크롤러가 구현해야 하는 표준 인터페이스
    
    향후 웹 API 전환 시에도 동일한 인터페이스로 일관성 유지
    """
    
    @abstractmethod
    def get_site_name(self) -> str:
        """크롤러가 담당하는 사이트 이름 반환"""
        pass
    
    @abstractmethod
    def get_site_key(self) -> str:
        """설정에서 사용하는 사이트 키 반환"""
        pass
    
    @abstractmethod
    def crawl(self, progress_callback=None, status_callback=None, **kwargs) -> pd.DataFrame:
        """
        크롤링 실행
        
        Args:
            progress_callback: 진행률 업데이트 콜백
            status_callback: 상태 메시지 업데이트 콜백
            **kwargs: 추가 파라미터
            
        Returns:
            크롤링된 데이터프레임
        """
        pass
    
    @abstractmethod
    def get_key_column(self) -> str:
        """데이터 중복 체크에 사용할 키 컬럼명 반환"""
        pass
    
    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """크롤링된 데이터의 유효성 검증"""
        pass
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 크롤링 설정 반환 (선택적 구현)"""
        return {}
    
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """데이터 전처리 (선택적 구현)"""
        return data
    
    def postprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """데이터 후처리 (선택적 구현)"""
        return data


class DataRepositoryInterface(ABC):
    """
    데이터 저장소 인터페이스 - Excel, SQLite, PostgreSQL 등 다양한 저장소 지원
    
    향후 DB 전환을 위한 추상화 계층
    """
    
    @abstractmethod
    def load_existing_data(self, site_key: str) -> pd.DataFrame:
        """기존 데이터 로드"""
        pass
    
    @abstractmethod
    def save_data(self, site_key: str, data: pd.DataFrame, is_incremental: bool = True) -> bool:
        """데이터 저장"""
        pass
    
    @abstractmethod
    def compare_and_get_new_entries(self, site_key: str, new_data: pd.DataFrame, key_column: str) -> pd.DataFrame:
        """신규 데이터 추출"""
        pass
    
    @abstractmethod
    def backup_data(self, site_key: str, data: pd.DataFrame) -> str:
        """데이터 백업"""
        pass
    
    @abstractmethod
    def get_statistics(self, site_key: str) -> Dict[str, Any]:
        """데이터 통계 정보 반환"""
        pass


class UIInterface(ABC):
    """
    UI 인터페이스 - tkinter, Flask, FastAPI 등 다양한 UI 프레임워크 지원
    
    향후 웹 인터페이스 전환을 위한 추상화 계층
    """
    
    @abstractmethod
    def show_message(self, message: str, message_type: str = "info") -> None:
        """메시지 표시"""
        pass
    
    @abstractmethod
    def update_progress(self, progress: int, message: str = "") -> None:
        """진행률 업데이트"""
        pass
    
    @abstractmethod
    def get_user_choice(self) -> str:
        """사용자 선택 반환"""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """UI 초기화"""
        pass
    
    @abstractmethod
    def run(self) -> None:
        """UI 실행"""
        pass