import sys
import os
import pandas as pd
from bs4 import BeautifulSoup
import requests
from typing import Optional

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.crawlers.base_crawler import BaseCrawler
from src.config.settings import BASE_URL, SECTIONS, DATA_COLUMNS, KEY_COLUMNS


class TaxTribunalCrawler(BaseCrawler):
    """
    조세심판원 크롤러
    
    세목별로 심판례를 크롤링하며, 여러 페이지에 걸쳐 데이터를 수집
    """
    
    def __init__(self):
        super().__init__("심판원", "tax_tribunal")
        self.base_url = BASE_URL
        self.sections = SECTIONS
    
    def get_key_column(self) -> str:
        return KEY_COLUMNS[self.site_key]
    
    def crawl(self, progress_callback=None, status_callback=None, **kwargs) -> pd.DataFrame:
        """조세심판원 크롤링 실행"""
        max_pages = kwargs.get('max_pages', self.config["max_pages"])
        
        self.update_status_safely(status_callback, f"{self.site_name} 크롤링 시작...")
        
        all_new_data = []
        total_sections = len(self.sections)
        
        for idx, section in enumerate(self.sections):
            section_data = self._crawl_section(
                section, max_pages, progress_callback, status_callback, 
                idx, total_sections
            )
            if not section_data.empty:
                all_new_data.append(section_data)
        
        if all_new_data:
            combined_data = pd.concat(all_new_data, ignore_index=True)
            # 전처리 및 후처리 적용
            combined_data = self.preprocess_data(combined_data)
            combined_data = self.postprocess_data(combined_data)
            
            self.update_status_safely(
                status_callback, 
                f"{self.site_name} 크롤링 완료: {len(combined_data)}개 사례 수집"
            )
            
            return combined_data
        else:
            self.update_status_safely(status_callback, f"{self.site_name} 크롤링 결과 없음")
            return pd.DataFrame(columns=DATA_COLUMNS[self.site_key])
    
    def _crawl_section(self, section: str, max_pages: int, progress_callback, 
                      status_callback, current_section_index: int, total_sections: int) -> pd.DataFrame:
        """특정 세목의 데이터 크롤링"""
        new_data = []
        total_cases = 0
        
        # 첫 번째 페이지에서 사례 수 확인
        params = {
            "pageNumber": 1, 
            "semok": section, 
            "cbSearchOption": "subject", 
            "cbJudge": "S500", 
            "rdView": "subject"
        }
        
        try:
            response = self._safe_request(f"{self.base_url}/mUser/dem/demList.do", params)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                cases = soup.select(".result-box")
                cases_per_page = len(cases)
                total_estimated_cases = cases_per_page * max_pages
            else:
                return pd.DataFrame()
        except Exception as e:
            print(f"세목 {section} 첫 페이지 조회 실패: {e}")
            return pd.DataFrame()
        
        # 페이지별 크롤링
        for page in range(1, max_pages + 1):
            try:
                params["pageNumber"] = page
                response = self._safe_request(f"{self.base_url}/mUser/dem/demList.do", params)
                
                if not response:
                    print(f"세목 {section} 페이지 {page} 조회 실패")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cases = soup.select(".result-box")
                
                for case in cases:
                    case_data = self._extract_case_data(case)
                    if case_data:
                        new_data.append(case_data)
                
                total_cases += len(cases)
                
                # 진행률 업데이트
                if total_estimated_cases > 0:
                    progress_value = int((total_cases / total_estimated_cases) * 100)
                    self.update_progress_safely(progress_callback, progress_value)
                
                # 상태 메시지 업데이트
                self.update_status_safely(
                    status_callback,
                    f"세목 {current_section_index + 1}/{total_sections} 진행 중: {total_cases}/{total_estimated_cases} 사례"
                )
                
            except Exception as e:
                print(f"세목 {section} 페이지 {page} 처리 중 오류: {e}")
                continue
        
        return pd.DataFrame(new_data, columns=DATA_COLUMNS[self.site_key])
    
    def _extract_case_data(self, case) -> Optional[dict]:
        """개별 사례 데이터 추출"""
        try:
            tax_label = case.select_one("span.label-tax")
            type_label = case.select_one("span.label-decision")
            date_element = case.select_one("p.date")
            case_number = case.select_one("p.case-num")
            title_element = case.select_one("a")
            
            if not all([tax_label, type_label, date_element, case_number, title_element]):
                return None
            
            tax = tax_label.get_text(strip=True)
            case_type = type_label.get_text(strip=True)
            decision_date = date_element.get_text(strip=True).replace("결정일", "").strip()
            claim_number = case_number.get_text(strip=True).replace("청구번호", "").strip()
            title = title_element.get_text(strip=True)
            link = self.base_url + title_element["href"] if title_element else ""
            
            return {
                "세목": tax,
                "유형": case_type,
                "결정일": decision_date,
                "청구번호": claim_number,
                "제목": title,
                "링크": link
            }
            
        except Exception as e:
            print(f"사례 데이터 추출 중 오류: {e}")
            return None
    
    def _safe_request(self, url: str, params: dict, retries: int = None, delay: int = None):
        """안전한 HTTP 요청"""
        if retries is None:
            retries = self.config["retry_count"]
        if delay is None:
            delay = self.config["retry_delay"]
        
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, timeout=self.config["timeout"])
                response.raise_for_status()
                return response
            except (requests.exceptions.RequestException, TimeoutError) as e:
                print(f"HTTP 요청 시도 {attempt + 1} 실패: {e}")
                if attempt < retries - 1:
                    print(f"{delay}초 후 재시도...")
                    import time
                    time.sleep(delay)
                else:
                    print("최대 재시도 횟수 도달. 요청 실패.")
                    return None
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """조세심판원 데이터 특화 검증"""
        if not super().validate_data(data):
            return False
        
        # 조세심판원 특화 검증
        required_columns = ["세목", "유형", "결정일", "청구번호", "제목"]
        for col in required_columns:
            if col not in data.columns:
                return False
        
        # 청구번호 형식 검증 (간단한 패턴 체크)
        if not data["청구번호"].str.contains(r'\d+').any():
            return False
        
        return True