"""
저장소 포트 인터페이스

Hexagonal Architecture의 포트 정의:
- IRepository: 데이터 영속성 인터페이스
- 도메인 코어는 이 인터페이스에만 의존, 구체적인 저장소(SQLite, Excel 등)에 의존하지 않음
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


class IRepository(ABC):
    """
    데이터 저장소 인터페이스 (Port)

    구현체 예시:
    - SQLiteRepository: 현재 메인 저장소
    - ExcelRepository: 백업용 저장소
    - InMemoryRepository: 테스트용

    사용 예:
        repo: IRepository = SQLiteRepository("data/tax_data.db")
        existing = repo.load_existing_data("nts_authority")
        repo.save_data("nts_authority", new_data)
    """

    @abstractmethod
    def load_existing_data(
        self,
        site_key: str,
        include_metadata: bool = False
    ) -> pd.DataFrame:
        """
        사이트별 기존 데이터 로드

        Args:
            site_key: 사이트 식별자
            include_metadata: 메타데이터(created_at 등) 포함 여부

        Returns:
            저장된 데이터 DataFrame (없으면 빈 DataFrame)
        """
        pass

    @abstractmethod
    def save_data(
        self,
        site_key: str,
        data: pd.DataFrame,
        mode: str = "append"
    ) -> int:
        """
        데이터 저장

        Args:
            site_key: 사이트 식별자
            data: 저장할 DataFrame
            mode: "append" (추가) 또는 "replace" (전체 교체)

        Returns:
            저장된 행 수
        """
        pass

    @abstractmethod
    def get_existing_keys(self, site_key: str, key_column: str) -> set:
        """
        기존 키 값 집합 조회 (중복 탐지용)

        Args:
            site_key: 사이트 식별자
            key_column: 키 컬럼명

        Returns:
            기존 키 값들의 집합
        """
        pass

    @abstractmethod
    def count(self, site_key: str) -> int:
        """
        사이트별 데이터 건수 조회

        Args:
            site_key: 사이트 식별자

        Returns:
            저장된 데이터 건수
        """
        pass

    def detect_new_entries(
        self,
        site_key: str,
        new_data: pd.DataFrame,
        key_column: str
    ) -> pd.DataFrame:
        """
        새로운 데이터 탐지 (기본 구현)

        Args:
            site_key: 사이트 식별자
            new_data: 새로 크롤링한 데이터
            key_column: 중복 제거용 키 컬럼

        Returns:
            기존에 없는 새로운 데이터만 포함한 DataFrame
        """
        if new_data.empty:
            return new_data

        existing_keys = self.get_existing_keys(site_key, key_column)

        if not existing_keys:
            return new_data

        # 기존에 없는 데이터만 필터링
        mask = ~new_data[key_column].isin(existing_keys)
        return new_data[mask].copy()


class IScheduleRepository(ABC):
    """스케줄 저장소 인터페이스"""

    @abstractmethod
    def get_schedules(self) -> List[Dict[str, Any]]:
        """모든 스케줄 조회"""
        pass

    @abstractmethod
    def save_schedule(self, site_key: str, schedule: Dict[str, Any]) -> bool:
        """스케줄 저장/수정"""
        pass

    @abstractmethod
    def delete_schedule(self, site_key: str) -> bool:
        """스케줄 삭제"""
        pass


class INotificationHistoryRepository(ABC):
    """알림 이력 저장소 인터페이스"""

    @abstractmethod
    def save_notification(
        self,
        site_key: str,
        notification_type: str,
        message: str,
        data_count: int
    ) -> int:
        """알림 이력 저장"""
        pass

    @abstractmethod
    def get_notifications(
        self,
        limit: int = 50,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """알림 이력 조회"""
        pass

    @abstractmethod
    def mark_as_read(self, notification_id: int) -> bool:
        """알림 읽음 처리"""
        pass
