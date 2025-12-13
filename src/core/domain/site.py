"""
사이트 도메인 모델

GPT-5.2 권장사항 반영:
- SiteDefinition: 크롤링에 필요한 최소 정의만 (도메인 코어)
- 프레젠테이션 필드(color, choice_number)는 config/sites.py로 분리
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SiteDefinition:
    """
    사이트 정의 - 크롤링에 필요한 최소 정보만 포함

    불변(frozen) Value Object로 설계:
    - 동일한 key를 가진 SiteDefinition은 동일한 객체로 취급
    - 생성 후 변경 불가

    Attributes:
        key: 사이트 고유 식별자 (예: "tax_tribunal", "nts_authority")
        url: 크롤링 대상 URL
        key_column: 중복 제거에 사용되는 키 컬럼 (예: "문서번호", "청구번호")
        data_columns: 크롤링 결과 DataFrame의 컬럼 순서
    """
    key: str
    url: str
    key_column: str
    data_columns: Tuple[str, ...]

    def __post_init__(self):
        """불변성 보장을 위한 tuple 변환 검증"""
        if not isinstance(self.data_columns, tuple):
            object.__setattr__(self, 'data_columns', tuple(self.data_columns))

    def __eq__(self, other):
        """key 기반 동등성 비교"""
        if not isinstance(other, SiteDefinition):
            return False
        return self.key == other.key

    def __hash__(self):
        """key 기반 해시"""
        return hash(self.key)

    def __repr__(self):
        return f"SiteDefinition(key='{self.key}')"
