"""
크롤링 결과 도메인 모델

GPT-5.2 권장사항 반영:
- CrawlStatistics: 크롤링 통계 (불변 Value Object)
- CrawlResult: 크롤링 실행 결과 (불변 Value Object)
- 도메인 코어에서 pandas 의존성 최소화 (Optional 타입 사용)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from enum import Enum


class CrawlStatus(Enum):
    """크롤링 상태 열거형"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # 일부 성공
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CrawlStatistics:
    """
    크롤링 통계 - 불변 Value Object

    Attributes:
        total_crawled: 크롤링된 총 항목 수
        new_count: 새로 발견된 항목 수
        existing_count: 기존 DB의 항목 수
        duplicate_count: 중복으로 필터링된 항목 수
        duration_seconds: 크롤링 소요 시간 (초)
    """
    total_crawled: int
    new_count: int
    existing_count: int
    duplicate_count: int
    duration_seconds: float = 0.0

    def __post_init__(self):
        """음수 값 검증"""
        if self.total_crawled < 0:
            raise ValueError("total_crawled cannot be negative")
        if self.new_count < 0:
            raise ValueError("new_count cannot be negative")
        if self.existing_count < 0:
            raise ValueError("existing_count cannot be negative")
        if self.duplicate_count < 0:
            raise ValueError("duplicate_count cannot be negative")

    @property
    def has_new_data(self) -> bool:
        """새로운 데이터가 있는지 확인"""
        return self.new_count > 0

    @property
    def success_rate(self) -> float:
        """성공률 계산 (0.0 ~ 1.0)"""
        if self.total_crawled == 0:
            return 0.0
        return (self.new_count + self.duplicate_count) / self.total_crawled

    def to_dict(self) -> dict:
        """딕셔너리 변환 (API 응답용)"""
        return {
            "total_crawled": self.total_crawled,
            "new_count": self.new_count,
            "existing_count": self.existing_count,
            "duplicate_count": self.duplicate_count,
            "duration_seconds": round(self.duration_seconds, 2),
            "has_new_data": self.has_new_data
        }


@dataclass(frozen=True)
class CrawlResult:
    """
    크롤링 실행 결과 - 불변 Value Object

    Attributes:
        site_key: 사이트 식별자 (예: "tax_tribunal", "nts_authority")
        status: 크롤링 상태
        statistics: 크롤링 통계
        new_entries: 새로 발견된 데이터 (pandas DataFrame 또는 None)
        error_message: 에러 발생 시 메시지
        crawled_at: 크롤링 완료 시간
    """
    site_key: str
    status: CrawlStatus
    statistics: CrawlStatistics
    new_entries: Optional[Any] = None  # pandas.DataFrame, 도메인에서 pandas 직접 참조 회피
    error_message: Optional[str] = None
    crawled_at: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        """성공 여부 확인"""
        return self.status == CrawlStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """에러 여부 확인"""
        return self.status == CrawlStatus.ERROR

    @property
    def has_new_data(self) -> bool:
        """새로운 데이터가 있는지 확인"""
        return self.statistics.has_new_data

    @classmethod
    def success(
        cls,
        site_key: str,
        statistics: CrawlStatistics,
        new_entries: Optional[Any] = None
    ) -> "CrawlResult":
        """성공 결과 팩토리 메서드"""
        return cls(
            site_key=site_key,
            status=CrawlStatus.SUCCESS,
            statistics=statistics,
            new_entries=new_entries
        )

    @classmethod
    def error(
        cls,
        site_key: str,
        error_message: str,
        partial_statistics: Optional[CrawlStatistics] = None
    ) -> "CrawlResult":
        """에러 결과 팩토리 메서드"""
        return cls(
            site_key=site_key,
            status=CrawlStatus.ERROR,
            statistics=partial_statistics or CrawlStatistics(0, 0, 0, 0, 0.0),
            error_message=error_message
        )

    def to_dict(self) -> dict:
        """딕셔너리 변환 (API 응답용)"""
        result = {
            "site_key": self.site_key,
            "status": self.status.value,
            "statistics": self.statistics.to_dict(),
            "crawled_at": self.crawled_at.isoformat(),
            "has_new_data": self.has_new_data
        }
        if self.error_message:
            result["error_message"] = self.error_message
        return result

    def __repr__(self) -> str:
        return (
            f"CrawlResult(site_key='{self.site_key}', "
            f"status={self.status.value}, "
            f"new_count={self.statistics.new_count})"
        )
