"""
사이트 카탈로그 및 디스플레이 설정

GPT-5.2 권장사항 반영:
- SiteCatalog: 불변 dict (전역 Registry 대신)
- SiteDisplay: UI/API용 프레젠테이션 정보 (도메인과 분리)
- 단일 소스: 모든 사이트 정보가 이 파일에 집중

사용법:
    from src.config.sites import SITE_CATALOG, SITE_DISPLAY, get_site, get_by_choice
"""

from dataclasses import dataclass
from typing import Dict, Optional
from src.core.domain.site import SiteDefinition


@dataclass(frozen=True)
class SiteDisplay:
    """
    UI/API용 사이트 표시 정보

    도메인 코어(SiteDefinition)와 분리된 프레젠테이션 계층
    """
    name: str           # 한글 표시명 (예: "조세심판원")
    color: str          # UI 색상 코드 (예: "#3B82F6")
    choice_number: str  # 레거시 선택 번호 (예: "1")


# =============================================================================
# SITE_CATALOG: 크롤링 도메인 정보 (단일 소스)
# =============================================================================

SITE_CATALOG: Dict[str, SiteDefinition] = {
    "tax_tribunal": SiteDefinition(
        key="tax_tribunal",
        url="https://www.tt.go.kr",
        key_column="청구번호",
        data_columns=("세목", "유형", "결정일", "청구번호", "제목", "링크")
    ),
    "nts_authority": SiteDefinition(
        key="nts_authority",
        url="https://taxlaw.nts.go.kr/qt/USEQTJ001M.do",
        key_column="문서번호",
        data_columns=("세목", "생산일자", "문서번호", "제목", "링크")
    ),
    "nts_precedent": SiteDefinition(
        key="nts_precedent",
        url="https://taxlaw.nts.go.kr/pd/USEPDI001M.do",
        key_column="문서번호",
        data_columns=("세목", "생산일자", "문서번호", "제목", "결론", "링크")
    ),
    "moef": SiteDefinition(
        key="moef",
        url="https://www.moef.go.kr/lw/intrprt/TaxLawIntrPrtCaseList.do",
        key_column="문서번호",
        data_columns=("문서번호", "회신일자", "제목", "링크")
    ),
    "mois": SiteDefinition(
        key="mois",
        url="https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000",
        key_column="문서번호",
        data_columns=("세목", "문서번호", "생산일자", "제목", "링크")
    ),
    "bai": SiteDefinition(
        key="bai",
        url="https://www.bai.go.kr/bai/exClaims/exClaims/list/",
        key_column="문서번호",
        data_columns=("청구분야", "문서번호", "결정일자", "제목")
    ),
    "scourt_major_decisions": SiteDefinition(
        key="scourt_major_decisions",
        url="https://www.scourt.go.kr",
        key_column="번호",
        data_columns=("번호", "작성일", "법원", "제목", "링크")
    ),
    "scourt_scheduled_decisions": SiteDefinition(
        key="scourt_scheduled_decisions",
        url="https://www.scourt.go.kr",
        key_column="고유키",
        data_columns=(
            "고유키", "선고일자", "재판부", "사건종류", "사건번호", "사건명",
            "조세관련", "관련키워드", "쟁점PDF", "보도자료링크"
        )
    ),
}


# =============================================================================
# SITE_DISPLAY: 프레젠테이션 정보 (UI/API용)
# =============================================================================

SITE_DISPLAY: Dict[str, SiteDisplay] = {
    "tax_tribunal": SiteDisplay(
        name="조세심판원",
        color="#3B82F6",
        choice_number="1"
    ),
    "nts_authority": SiteDisplay(
        name="국세청 유권해석",
        color="#10B981",
        choice_number="2"
    ),
    "nts_precedent": SiteDisplay(
        name="국세청 판례",
        color="#8B5CF6",
        choice_number="4"
    ),
    "moef": SiteDisplay(
        name="기획재정부",
        color="#F59E0B",
        choice_number="3"
    ),
    "mois": SiteDisplay(
        name="행정안전부",
        color="#EF4444",
        choice_number="5"
    ),
    "bai": SiteDisplay(
        name="감사원",
        color="#6366F1",
        choice_number="6"
    ),
    "scourt_major_decisions": SiteDisplay(
        name="전국법원 주요판결",
        color="#0F766E",
        choice_number="8"
    ),
    "scourt_scheduled_decisions": SiteDisplay(
        name="대법원 선고예정 판결",
        color="#B45309",
        choice_number="9"
    ),
}


# =============================================================================
# 헬퍼 함수 (전역 Registry 대신 순수 함수)
# =============================================================================

def get_site(key: str) -> SiteDefinition:
    """
    사이트 키로 SiteDefinition 조회

    Args:
        key: 사이트 키 (예: "tax_tribunal")

    Returns:
        SiteDefinition 객체

    Raises:
        KeyError: 존재하지 않는 키
    """
    if key not in SITE_CATALOG:
        raise KeyError(f"Unknown site key: {key}")
    return SITE_CATALOG[key]


def get_display(key: str) -> SiteDisplay:
    """
    사이트 키로 SiteDisplay 조회

    Args:
        key: 사이트 키 (예: "tax_tribunal")

    Returns:
        SiteDisplay 객체

    Raises:
        KeyError: 존재하지 않는 키
    """
    if key not in SITE_DISPLAY:
        raise KeyError(f"Unknown site key: {key}")
    return SITE_DISPLAY[key]


def get_by_choice(choice: str) -> SiteDefinition:
    """
    레거시 선택 번호로 SiteDefinition 조회

    Args:
        choice: 선택 번호 (예: "1", "2", ...)

    Returns:
        SiteDefinition 객체

    Raises:
        KeyError: 존재하지 않는 선택 번호
    """
    for key, display in SITE_DISPLAY.items():
        if display.choice_number == choice:
            return SITE_CATALOG[key]
    raise KeyError(f"Unknown choice number: {choice}")


def get_key_by_choice(choice: str) -> str:
    """
    레거시 선택 번호로 사이트 키 조회

    Args:
        choice: 선택 번호 (예: "1", "2", ...)

    Returns:
        사이트 키 문자열

    Raises:
        KeyError: 존재하지 않는 선택 번호
    """
    for key, display in SITE_DISPLAY.items():
        if display.choice_number == choice:
            return key
    raise KeyError(f"Unknown choice number: {choice}")


def get_choice_by_key(key: str) -> str:
    """
    사이트 키로 레거시 선택 번호 조회

    Args:
        key: 사이트 키 (예: "tax_tribunal")

    Returns:
        선택 번호 문자열 (예: "1")

    Raises:
        KeyError: 존재하지 않는 사이트 키
    """
    if key not in SITE_DISPLAY:
        raise KeyError(f"Unknown site key: {key}")
    return SITE_DISPLAY[key].choice_number


def all_site_keys() -> list:
    """모든 사이트 키 목록 반환"""
    return list(SITE_CATALOG.keys())


def all_sites() -> list:
    """모든 SiteDefinition 목록 반환"""
    return list(SITE_CATALOG.values())


# =============================================================================
# 하위 호환성을 위한 매핑 (점진적 마이그레이션용)
# 향후 삭제 예정
# =============================================================================

def get_legacy_urls() -> dict:
    """settings.py의 URLS 형식으로 변환 (하위 호환)"""
    return {key: site.url for key, site in SITE_CATALOG.items()}


def get_legacy_data_columns() -> dict:
    """settings.py의 DATA_COLUMNS 형식으로 변환 (하위 호환)"""
    return {key: list(site.data_columns) for key, site in SITE_CATALOG.items()}


def get_legacy_key_columns() -> dict:
    """settings.py의 KEY_COLUMNS 형식으로 변환 (하위 호환)"""
    return {key: site.key_column for key, site in SITE_CATALOG.items()}


def get_legacy_site_info() -> dict:
    """app.py의 BASE_SITE_INFO 형식으로 변환 (하위 호환)"""
    return {
        key: {"name": display.name, "color": display.color}
        for key, display in SITE_DISPLAY.items()
    }
