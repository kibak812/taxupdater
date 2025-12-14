"""
웹 환경용 레거시 크롤러들
tkinter 의존성 없이 작동하는 크롤링 함수들
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import sys
import os

# 상위 디렉토리 설정 import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.config.settings import (
    URLS, SECTIONS, CRAWLING_CONFIG, 
    BAI_CLAIM_TYPES, SELENIUM_OPTIONS
)

# 웹 환경용 가짜 progress/status 클래스
class WebProgress:
    def __init__(self):
        self.value = 0
    
    def update(self):
        pass

class WebStatus:
    def __init__(self):
        self.text = ""
    
    def config(self, text):
        self.text = text
        print(f"[크롤링 상태] {text}")
    
    def update(self):
        pass

# 재시도 로직
def safe_request(url, params, retries=None, delay=None):
    if retries is None:
        retries = CRAWLING_CONFIG["retry_count"]
    if delay is None:
        delay = CRAWLING_CONFIG["retry_delay"]
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=CRAWLING_CONFIG["timeout"])
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, TimeoutError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Exiting.")
                return None


def crawl_moef_site(progress=None, status_message=None, **kwargs):
    """기획재정부 크롤링 (example.py 기반)"""
    print("[INFO] 기획재정부 크롤링 시작...")
    
    if progress is None:
        progress = WebProgress()
    if status_message is None:
        status_message = WebStatus()
    
    status_message.config("기획재정부 데이터 크롤링 중...")
    
    # example.py의 crawl_moef_site 로직 사용
    max_pages = kwargs.get('max_pages', 10)
    moef_url_template = "https://www.moef.go.kr/lw/intrprt/TaxLawIntrPrtCaseList.do?bbsId=MOSFBBS_000000000237&menuNo=8120300&pageIndex={page}"
    all_items = []
    total_items = 0
    items_per_page = 10
    
    # 예상 총 항목 수 계산
    total_estimated_items = items_per_page * max_pages
    
    for page in range(1, max_pages + 1):
        if status_message:
            status_message.config(f"기획재정부 페이지 {page}/{max_pages} 크롤링 중...")
        
        current_url = moef_url_template.format(page=page)
        response = safe_request(current_url, params={}, retries=3, delay=2)
        
        if not response:
            print(f"Failed to fetch page {page} from MOEF site. Skipping.")
            continue
            
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select("ul.boardType3.explnList > li")
        
        if not items:
            print(f"No items found on page {page}. This might be the last page.")
            break
            
        for item in items:
            title_element = item.select_one("h3 > a")
            doc_num_element = item.select_one("span.depart")
            date_element = item.select_one("span.date")
            
            if not all([title_element, doc_num_element, date_element]):
                continue
                
            title = title_element.get_text(strip=True)
            doc_num = doc_num_element.get_text(strip=True)
            response_date = date_element.get_text(strip=True).replace("회신일자 :", "").strip()
            
            # 링크 추출 - onclick 속성에서 fn_egov_select('MOSF_ID') 형태로 ID 추출
            link = ""
            onclick_attr = title_element.get('onclick')
            if onclick_attr and "fn_egov_select" in onclick_attr:
                # fn_egov_select('MOSF_000000000073953') 에서 MOSF_000000000073953 추출
                import re
                select_match = re.search(r"fn_egov_select\(['\"]([^'\"]+)['\"]\)", onclick_attr)
                if select_match:
                    mosf_id = select_match.group(1)
                    link = f"https://www.moef.go.kr/lw/intrprt/TaxLawIntrPrtCaseView.do?bbsId=MOSFBBS_000000000237&searchNttId1={mosf_id}&menuNo=8120300"
            
            all_items.append({
                "문서번호": doc_num,
                "회신일자": response_date,
                "제목": title,
                "링크": link
            })
        
        total_items += len(items)
        
        # 진행 상태 업데이트
        if progress:
            progress.value = int((total_items / total_estimated_items) * 100)
            progress.update()
    
    if status_message:
        status_message.config(f"기획재정부 크롤링 완료: 총 {total_items}개 항목 수집")
        
    return pd.DataFrame(all_items)

def crawl_mois_site(progress=None, status_message=None, **kwargs):
    """행정안전부 크롤링 (example.py 기반)"""
    print("[INFO] 행정안전부 크롤링 시작...")
    
    if progress is None:
        progress = WebProgress()
    if status_message is None:
        status_message = WebStatus()
    
    # example.py의 crawl_mois_site 로직 사용
    max_pages = kwargs.get('max_pages', 5)
    mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000"
    
    options = Options()
    for option in SELENIUM_OPTIONS:
        options.add_argument(option)
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(mois_url)
        
        if status_message:
            status_message.config("행정안전부 데이터 로딩 중...")
        
        time.sleep(10)  # JavaScript 실행을 위한 더 긴 대기시간
        
        all_items = []
        page = 1
        
        while page <= max_pages:
            try:
                if status_message:
                    status_message.config(f"행정안전부 페이지 {page}/{max_pages} 크롤링 중...")
                
                # 첫 페이지에서 HTML 구조 분석
                if page == 1:
                    print("행정안전부 페이지 HTML 구조 분석 중...")
                    page_source = driver.page_source[:3000]  # 처음 3000자만 출력
                    print("페이지 소스 샘플:")
                    print(page_source)
                
                # 정확한 선택자로 리스트 항목 찾기
                items = driver.find_elements(By.CSS_SELECTOR, "ul.search_out.exp li")
                
                if not items:
                    print(f"행정안전부 페이지 {page}: 'ul.search_out.exp li' 선택자로 항목을 찾을 수 없음")
                    break
                
                
                page_items_count = 0
                for item in items:
                    try:
                        # HTML 구조에 따른 정확한 데이터 추출
                        first_p = item.find_element(By.TAG_NAME, "p")
                        
                        # 세목 추출 (span.part)
                        try:
                            tax_span = first_p.find_element(By.CSS_SELECTOR, "span.part")
                            tax_category = tax_span.text.strip()
                        except:
                            tax_category = ""
                        
                        # 첫 번째 p 태그의 전체 텍스트에서 문서번호와 날짜 추출
                        first_p_text = first_p.text.strip()
                        
                        # 정규식으로 날짜 패턴 찾기
                        import re
                        date_pattern = r'\((\d{4}\.\d{2}\.\d{2})\)'
                        date_match = re.search(date_pattern, first_p_text)
                        
                        if date_match:
                            date_part = date_match.group(1)
                            # 세목 이후부터 날짜 이전까지가 문서번호
                            before_date = first_p_text[:date_match.start()].strip()
                            # 세목을 제거하고 문서번호만 추출
                            if tax_category:
                                doc_number = before_date.replace(tax_category, "").strip()
                            else:
                                doc_number = before_date
                        else:
                            date_part = ""
                            doc_number = ""
                        
                        # 제목 및 링크 추출 (p.tt a)
                        try:
                            title_element = item.find_element(By.CSS_SELECTOR, "p.tt a")
                            title = title_element.text.strip()
                            
                            # 링크 추출 - onclick 속성에서 authoritativePopUp(번호) 형태로 번호 추출
                            link = ""
                            onclick_attr = title_element.get_attribute("onclick")
                            if onclick_attr and "authoritativePopUp" in onclick_attr:
                                popup_match = re.search(r'authoritativePopUp\((\d+)\)', onclick_attr)
                                if popup_match:
                                    doc_id = popup_match.group(1)
                                    link = f"https://www.olta.re.kr/explainInfo/authoInterpretationDetail.do?num={doc_id}"
                        except:
                            title = ""
                            link = ""
                        
                        # 유효한 데이터인지 확인
                        if doc_number and title and date_part:
                            all_items.append({
                                "세목": tax_category,
                                "문서번호": doc_number,
                                "생산일자": date_part,
                                "제목": title,
                                "링크": link
                            })
                            page_items_count += 1
                            
                    except Exception as e:
                        print(f"항목 처리 중 오류: {e}")
                        continue
                
                print(f"행정안전부 페이지 {page}: {page_items_count}개 항목 추출")
                
                if page_items_count == 0:
                    print(f"행정안전부 페이지 {page}: 데이터 없음, 중단")
                    break
                
                # 다음 페이지로 이동
                if page < max_pages:
                    try:
                        # JavaScript doPaging 함수 호출
                        page_param = page * 10  # 페이지 번호는 10단위로 증가 (10, 20, 30...)
                        print(f"행정안전부 페이지 이동: doPaging('{page_param}')")
                        driver.execute_script(f"doPaging('{page_param}')")
                        time.sleep(3)
                        page += 1
                    except Exception as e:
                        print(f"행정안전부 페이지 이동 실패: {e}")
                        break
                else:
                    break
                
                if progress:
                    progress.value = int((page / max_pages) * 100)
                    progress.update()
                    
            except Exception as e:
                print(f"행정안전부 페이지 {page} 처리 중 오류: {e}")
                break
        
        if status_message:
            status_message.config(f"행정안전부 크롤링 완료: 총 {len(all_items)}개 항목 수집")
        
        print(f"행정안전부: 총 {len(all_items)}개 항목 수집 완료")
        
        return pd.DataFrame(all_items, columns=["세목", "문서번호", "생산일자", "제목", "링크"])

    finally:
        driver.quit()

def crawl_bai_site(progress=None, status_message=None, **kwargs):
    """감사원 크롤링 (example.py 기반)"""
    print("[INFO] 감사원 크롤링 시작...")
    
    if progress is None:
        progress = WebProgress()
    if status_message is None:
        status_message = WebStatus()
    
    # example.py의 crawl_bai_site 로직 사용
    max_pages = kwargs.get('max_pages', 10)
    bai_url = "https://www.bai.go.kr/bai/exClaims/exClaims/list/"
    
    options = Options()
    for option in SELENIUM_OPTIONS:
        options.add_argument(option)
    driver = webdriver.Chrome(options=options)
    
    # 청구분야 목록 (조세 관련만) - 실제 사이트 값으로 수정
    claim_types = [
        {"name": "국세", "value": "10"},
        {"name": "지방세", "value": "20"}
    ]
    
    try:
        all_data = []
        
        for claim_type in claim_types:
            if status_message:
                status_message.config(f"감사원 {claim_type['name']} 데이터 로딩 중...")
            
            print(f"감사원 {claim_type['name']} 분야 크롤링 시작")
            
            driver.get(bai_url)
            
            # 페이지 로딩 대기
            try:
                WebDriverWait(driver, 15).until(
                    lambda driver: driver.find_elements(By.CSS_SELECTOR, "select#reqDvsnCd") or
                                   driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                )
            except:
                print("감사원 사이트 로딩 실패, 기본 대기 후 진행")
                time.sleep(5)
            
            # 드롭다운 선택 및 검색 방식
            try:
                # 드롭다운 선택
                select_element = driver.find_element(By.CSS_SELECTOR, "select#reqDvsnCd")
                from selenium.webdriver.support.ui import Select
                select = Select(select_element)
                select.select_by_value(claim_type["value"])
                print(f"청구분야 '{claim_type['name']}' 드롭다운 선택 완료")
                time.sleep(2)
                
                # 검색 버튼 클릭
                search_button = driver.find_element(By.CSS_SELECTOR, "div.searchForm button[type='button']")
                driver.execute_script("arguments[0].click();", search_button)
                print(f"청구분야 '{claim_type['name']}' 검색 버튼 클릭 완료")
                time.sleep(3)
                
            except Exception as e:
                print(f"청구분야 '{claim_type['name']}' 드롭다운/검색 실패: {e}")
                continue
            
            # 해당 분야에서 페이지별 데이터 수집
            page = 1
            pages_per_type = 5  # 각 분야별로 5페이지씩
            
            while page <= pages_per_type:
                try:
                    if status_message:
                        status_message.config(f"감사원 {claim_type['name']} 페이지 {page}/{pages_per_type} 크롤링 중...")
                    
                    # 여러 가능한 테이블 선택자 시도
                    items = []
                    possible_selectors = [
                        "table tbody tr",
                        "table.board-list tbody tr", 
                        "table.tbl-list tbody tr",
                        ".board-list tbody tr",
                        "tbody tr"
                    ]
                    
                    for selector in possible_selectors:
                        items = driver.find_elements(By.CSS_SELECTOR, selector)
                        if items:
                            print(f"감사원: '{selector}' 선택자로 {len(items)}개 항목 발견")
                            break
                    
                    if not items:
                        print(f"감사원 {claim_type['name']} 페이지 {page}: 데이터를 찾을 수 없음")
                        break
                    
                    page_data_count = 0
                    for item in items:
                        try:
                            cells = item.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 4:  # 최소 4개 열 필요
                                # 정확한 테이블 구조에 따른 데이터 추출
                                doc_number = cells[0].text.strip()      # 결정번호
                                decision_date = cells[1].text.strip()   # 결정일자
                                category = cells[2].text.strip()        # 구분
                                
                                # 제목 추출 (p.answer는 제외하고 제목만)
                                title_cell = cells[3]
                                try:
                                    # p.answer 요소가 있다면 제외하고 제목만 추출
                                    answer_p = title_cell.find_element(By.CSS_SELECTOR, "p.answer")
                                    full_text = title_cell.text.strip()
                                    answer_text = answer_p.text.strip()
                                    title = full_text.replace(answer_text, "").strip()
                                except:
                                    # p.answer가 없다면 전체 텍스트가 제목
                                    title = title_cell.text.strip()
                                
                                # 결정번호 형식 확인 (2025-심사-271 같은 형식)
                                if doc_number and title and ("-" in doc_number and ("심사" in doc_number or "결정" in doc_number)):
                                    all_data.append({
                                        "청구분야": claim_type['name'],
                                        "문서번호": doc_number,
                                        "결정일자": decision_date,
                                        "제목": title
                                    })
                                    page_data_count += 1
                                    
                        except Exception as e:
                            if page == 1:
                                print(f"항목 처리 중 오류: {e}")
                            continue
                    
                    print(f"감사원 {claim_type['name']} 페이지 {page}: {page_data_count}개 항목 수집")
                    
                    if page_data_count == 0:
                        print(f"감사원 {claim_type['name']} 페이지 {page}: 데이터 없음, 다음 페이지 시도")
                    
                    # 다음 페이지로 이동
                    if page < pages_per_type:
                        try:
                            next_page_num = page + 1
                            print(f"감사원 {claim_type['name']} 페이지 이동: {next_page_num}페이지")
                            page_link = driver.find_element(By.XPATH, f"//ul[@class='pages']//a[text()='{next_page_num}']")
                            page_link.click()
                            time.sleep(3)
                            page += 1
                        except Exception as e:
                            print(f"감사원 {claim_type['name']} 페이지 이동 실패: {e}")
                            break
                    else:
                        break
                        
                except Exception as e:
                    print(f"감사원 {claim_type['name']} 페이지 {page} 처리 중 오류: {e}")
                    break
            
            print(f"감사원 {claim_type['name']} 분야 완료: {len([item for item in all_data if item.get('청구분야') == claim_type['name']])}개 항목 수집")
            
            # 진행률 업데이트
            if progress:
                current_progress = (claim_types.index(claim_type) + 1) / len(claim_types) * 100
                progress.value = int(current_progress)
                progress.update()
        
        if status_message:
            status_message.config(f"감사원 크롤링 완료: 총 {len(all_data)}개 사례 수집")
        
        print(f"감사원 전체 크롤링 완료:")
        for claim_type in claim_types:
            type_count = len([item for item in all_data if item.get('청구분야') == claim_type['name']])
            print(f"  {claim_type['name']}: {type_count}개")
        print(f"  전체: {len(all_data)}개 항목")
        
        return pd.DataFrame(all_data, columns=["청구분야", "문서번호", "결정일자", "제목"])

    finally:
        driver.quit()

# 테스트용 함수
if __name__ == "__main__":
    print("웹 레거시 크롤러 테스트...")
    
    # 간단한 테스트
    result = crawl_moef_site()
    print(f"기재부 테스트 결과: {len(result)}개")
    print(result.head() if not result.empty else "데이터 없음")