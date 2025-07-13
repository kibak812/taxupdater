"""
국세법령정보시스템 링크 생성 유틸리티
문서번호를 기반으로 검색결과창 링크를 생성합니다.
"""
import urllib.parse
from typing import Optional


def generate_nts_search_link(doc_number: str, site_type: str = "authority") -> Optional[str]:
    """
    국세청 문서번호를 기반으로 검색 링크 생성
    
    Args:
        doc_number (str): 문서번호 (예: 기준-2025-법규재산-0071)
        site_type (str): 사이트 타입 ("authority" 또는 "precedent")
    
    Returns:
        Optional[str]: 생성된 검색 링크 또는 None (실패시)
    
    Examples:
        >>> generate_nts_search_link("기준-2025-법규재산-0071")
        'https://taxlaw.nts.go.kr/is/USEISA001M.do?schVcb=기준-2025-법규재산-0071&searchType=totalSearch'
    """
    if not doc_number or not doc_number.strip():
        return None
    
    try:
        # 문서번호 URL 인코딩
        encoded_doc_number = urllib.parse.quote(doc_number.strip(), safe='')
        
        # 검색 URL 생성
        base_url = "https://taxlaw.nts.go.kr/is/USEISA001M.do"
        search_url = f"{base_url}?schVcb={encoded_doc_number}&searchType=totalSearch"
        
        return search_url
        
    except Exception as e:
        print(f"링크 생성 실패 - 문서번호: {doc_number}, 오류: {e}")
        return None


def validate_nts_link(link: str) -> bool:
    """
    국세청 검색 링크 유효성 검증
    
    Args:
        link (str): 검증할 링크
    
    Returns:
        bool: 유효한 링크인지 여부
    """
    if not link:
        return False
    
    required_components = [
        "https://taxlaw.nts.go.kr/is/USEISA001M.do",
        "schVcb=",
        "searchType=totalSearch"
    ]
    
    return all(component in link for component in required_components)


def update_document_link(doc_number: str, current_link: str = "") -> str:
    """
    문서 링크 업데이트 (기존 링크가 없거나 잘못된 경우)
    
    Args:
        doc_number (str): 문서번호
        current_link (str): 현재 링크 (기본값: 빈 문자열)
    
    Returns:
        str: 업데이트된 링크 또는 기존 링크
    """
    # 기존 링크가 유효하면 그대로 유지
    if current_link and validate_nts_link(current_link):
        return current_link
    
    # 새로운 링크 생성
    new_link = generate_nts_search_link(doc_number)
    return new_link if new_link else current_link


if __name__ == "__main__":
    # 테스트 코드
    test_cases = [
        "기준-2025-법규재산-0071",
        "서면-2025-소비-1973", 
        "사전-2025-법규재산-0418",
        "2023구합49",
        "2024가합51235"
    ]
    
    print("=== 국세청 링크 생성 테스트 ===")
    for doc_num in test_cases:
        link = generate_nts_search_link(doc_num)
        valid = validate_nts_link(link) if link else False
        print(f"문서번호: {doc_num}")
        print(f"링크: {link}")
        print(f"유효성: {valid}")
        print("-" * 50)