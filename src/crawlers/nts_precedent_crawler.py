import sys
import os
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import Optional

# 상위 디렉토리 모듈 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.crawlers.base_crawler import BaseCrawler
from src.config.settings import URLS, DATA_COLUMNS, KEY_COLUMNS


class NTSPrecedentCrawler(BaseCrawler):
    """
    국세청 판례 크롤러
    
    동적 JavaScript 사이트에서 "더보기" 버튼을 통해 데이터를 로드하며,
    대량의 판례 데이터를 효율적으로 수집
    """
    
    def __init__(self):
        super().__init__("국세청 판례", "nts_precedent")
        self.url = URLS[self.site_key]
    
    def get_key_column(self) -> str:
        return KEY_COLUMNS[self.site_key]
    
    def crawl(self, progress_callback=None, status_callback=None, **kwargs) -> pd.DataFrame:
        """국세청 판례 크롤링 실행"""
        max_items = kwargs.get('max_items', self.config["max_items"])
        max_load_attempts = kwargs.get('max_load_attempts', self.config.get("max_load_attempts", 500))
        
        self.update_status_safely(status_callback, f"{self.site_name} 데이터 로딩 중...")
        
        driver = self.get_selenium_driver()
        
        try:
            # 타임아웃 설정
            driver.set_page_load_timeout(self.config.get("page_load_timeout", 60))
            driver.implicitly_wait(10)
            
            driver.get(self.url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "more_show"))
            )
            
            # 1단계: 데이터 로딩
            total_cases = self._load_data(driver, max_items, max_load_attempts, status_callback)
            
            # 2단계: 데이터 추출
            self.update_status_safely(
                status_callback, 
                f"{self.site_name} 데이터 처리 중... (총 {total_cases}개 항목)"
            )
            
            raw_data = self._extract_data(driver, progress_callback)
            
            # 3단계: 데이터 정리 및 중복 제거
            cleaned_data = self._clean_data(raw_data)
            
            self.update_progress_safely(progress_callback, 100)
            self.update_status_safely(
                status_callback,
                f"{self.site_name} 크롤링 완료: 총 {len(cleaned_data)}개 사례 수집"
            )
            
            return cleaned_data
            
        except Exception as e:
            print(f"{self.site_name} 크롤링 중 오류: {e}")
            return pd.DataFrame(columns=DATA_COLUMNS[self.site_key])
        finally:
            driver.quit()
    
    def _load_data(self, driver, max_items: int, max_load_attempts: int, status_callback) -> int:
        """더보기 버튼을 통해 데이터 로딩"""
        total_cases = 0
        current_attempt = 0
        
        while total_cases < max_items and current_attempt < max_load_attempts:
            try:
                current_attempt += 1
                cases = driver.find_elements(By.CSS_SELECTOR, "#bdltCtl > li")
                total_cases = len(cases)
                
                if total_cases >= max_items:
                    break
                
                # 더보기 버튼 클릭
                try:
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "more_show"))
                    )
                    driver.execute_script("arguments[0].click();", load_more_button)
                    
                    # 5번마다 상태 업데이트 (성능 최적화)
                    if current_attempt % 5 == 0:
                        self.update_status_safely(
                            status_callback,
                            f"{self.site_name} 데이터 로딩 중: {total_cases}/{max_items} 사례"
                        )
                    
                    time.sleep(1)  # 로딩 대기
                    
                except Exception as e:
                    print(f"더 이상 항목을 로드할 수 없습니다: {e}")
                    break
                    
            except Exception as e:
                print(f"데이터 로드 중 오류 발생: {e}")
                time.sleep(2)
        
        return total_cases
    
    def _extract_data(self, driver, progress_callback) -> list:
        """JavaScript를 사용하여 데이터 추출"""
        js_script = """
        const items = document.querySelectorAll("#bdltCtl > li");
        
        // nav 요소들로부터 ntstDcmId 매핑 구성
        const navElements = document.querySelectorAll("nav [data-ntstdcmid]");
        const navMap = new Map();
        navElements.forEach((navEl) => {
            const navTitle = navEl.textContent.trim();
            const ntstDcmId = navEl.getAttribute("data-ntstdcmid");
            if (navTitle && ntstDcmId) {
                navMap.set(navTitle, ntstDcmId);
            }
        });
        
        const result = Array.from(items).map((item, index) => {
            try {
                const taxLabel = item.querySelector("ul.legislation_list li:nth-child(2)").getAttribute("title").trim();
                const productionDate = item.querySelector("ul.subs_detail li span.num").textContent.trim();
                const docNumber = item.querySelector("ul.subs_detail li strong").textContent.trim();
                const title = item.querySelector("a.subs_title strong").textContent.trim();
                
                // ntstDcmId 추출
                let ntstDcmId = "";
                let link = "";
                
                // onclick 속성에서 추출 시도
                const clickableElement = item.querySelector("a.subs_title");
                if (clickableElement) {
                    const onclickAttr = clickableElement.getAttribute("onclick");
                    if (onclickAttr && onclickAttr.includes("ntstDcmId")) {
                        const match = onclickAttr.match(/ntstDcmId['"]\s*:\s*['"]([^'"]+)['"]/);
                        if (match) {
                            ntstDcmId = match[1];
                        }
                    }
                }
                
                // navMap에서 제목으로 매칭
                if (!ntstDcmId && navMap.has(title)) {
                    ntstDcmId = navMap.get(title);
                }
                
                // 판례용 링크 생성
                if (ntstDcmId) {
                    link = `https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=${ntstDcmId}&wnkey=f3fe8963-8e4b-4831-b9e6-59ec0ebe328c`;
                }
                
                return {taxLabel, productionDate, docNumber, title, link};
            } catch (e) {
                return {error: e.toString()};
            }
        });
        
        return result;
        """
        
        raw_items = driver.execute_script(js_script)
        return raw_items
    
    def _clean_data(self, raw_items: list) -> pd.DataFrame:
        """데이터 정리 및 중복 제거"""
        data = []
        doc_numbers_set = set()
        
        for idx, item in enumerate(raw_items):
            if 'error' in item:
                continue
            
            doc_number = item.get('docNumber', '')
            if doc_number and doc_number not in doc_numbers_set:
                doc_numbers_set.add(doc_number)
                data.append({
                    "세목": item.get('taxLabel', ''),
                    "생산일자": item.get('productionDate', ''),
                    "문서번호": doc_number,
                    "제목": item.get('title', ''),
                    "링크": item.get('link', '')
                })
        
        df = pd.DataFrame(data, columns=DATA_COLUMNS[self.site_key])
        
        # 전처리 및 후처리 적용
        df = self.preprocess_data(df)
        df = self.postprocess_data(df)
        
        print(f"{self.site_name}: 총 {len(raw_items)}개 항목 중 {len(df)}개 고유 항목 수집 완료")
        
        return df
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """국세청 판례 데이터 특화 검증"""
        if not super().validate_data(data):
            return False
        
        # 국세청 판례 특화 검증
        required_columns = ["세목", "생산일자", "문서번호", "제목"]
        for col in required_columns:
            if col not in data.columns:
                return False
        
        # 문서번호 형식 검증
        if not data["문서번호"].str.len().gt(0).any():
            return False
        
        return True