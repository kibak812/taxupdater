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

    동등성 설계 (Design Decision):
        key만으로 동등성을 비교합니다. 이는 의도적인 설계로,
        SITE_CATALOG에서 key로 조회하는 패턴에 최적화되어 있습니다.

        Martin Fowler의 관점에서 이는 Value Object보다 Entity에
        가깝지만, 현재 사용 패턴(Dict[str, SiteDefinition])에서는
        key 기반 동등성이 더 실용적입니다.

        향후 SiteDefinition을 set이나 캐시 키로 사용할 경우,
        모든 속성 기반 동등성으로 변경을 고려하세요.

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
