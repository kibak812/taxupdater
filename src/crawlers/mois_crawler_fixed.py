"""
행정안전부 크롤러 (수정된 버전)
HTML 구조에 맞게 새롭게 작성된 크롤러
"""

import time
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def crawl_mois_site_fixed(progress=None, status_message=None, max_pages=5):
    """
    행정안전부 크롤링 (HTML 구조에 맞게 수정된 버전)
    
    HTML 구조:
    <ul class="search_out exp">
        <li>
            <p><span class="part">취득세</span>문서번호 (날짜)</p>
            <p class="tt"><a onclick="authoritativePopUp(번호)">제목</a></p>
            <p class="txt"><a>내용요약</a></p>
        </li>
    </ul>
    """
    print("🔍 행정안전부 크롤링 시작 (수정된 버전)...")
    
    # WebProgress, WebStatus 클래스 정의
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
    
    if progress is None:
        progress = WebProgress()
    if status_message is None:
        status_message = WebStatus()
    
    mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000"
    
    # Selenium 설정
    options = Options()
    selenium_options = [
        "--headless",
        "--no-sandbox", 
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1920,1080"
    ]
    
    for option in selenium_options:
        options.add_argument(option)
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(mois_url)
        
        if status_message:
            status_message.config("행정안전부 데이터 로딩 중...")
        
        # 페이지 로딩 대기 - 더 긴 시간
        print("페이지 로딩 대기 중...")
        time.sleep(15)
        
        # JavaScript 실행 완료까지 추가 대기
        driver.execute_script("return document.readyState") 
        time.sleep(5)
        
        all_items = []
        page = 1
        
        while page <= max_pages:
            try:
                if status_message:
                    status_message.config(f"행정안전부 페이지 {page}/{max_pages} 크롤링 중...")
                
                # 첫 페이지에서 HTML 구조 분석
                if page == 1:
                    print("행정안전부 페이지 HTML 구조 분석 중...")
                    
                    # 현재 URL 확인
                    current_url = driver.current_url
                    print(f"현재 URL: {current_url}")
                    
                    # 페이지 소스 샘플 확인
                    page_source = driver.page_source
                    print(f"페이지 길이: {len(page_source)}")
                    print("페이지 소스 샘플:")
                    print(page_source[:2000])
                    
                    # search_out 키워드 찾기
                    if "search_out" in page_source:
                        print("✓ 페이지에 'search_out' 클래스 존재")
                    else:
                        print("✗ 페이지에 'search_out' 클래스 없음")
                    
                    # exp 키워드 찾기  
                    if "exp" in page_source:
                        print("✓ 페이지에 'exp' 클래스 존재")
                    else:
                        print("✗ 페이지에 'exp' 클래스 없음")
                    
                    try:
                        # 페이지가 완전히 로드될 때까지 대기
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.search_out.exp"))
                        )
                        print("✓ ul.search_out.exp 요소 발견!")
                    except:
                        print("✗ ul.search_out.exp 요소를 찾을 수 없음")
                        
                        # 대안 선택자들 시도
                        alternative_selectors = [
                            "ul.search_out",
                            ".search_out", 
                            "ul",
                            "li"
                        ]
                        
                        for selector in alternative_selectors:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                print(f"✓ '{selector}' 선택자로 {len(elements)}개 요소 발견")
                            else:
                                print(f"✗ '{selector}' 선택자로 요소 없음")
                
                # 정확한 선택자로 리스트 항목 찾기
                items = driver.find_elements(By.CSS_SELECTOR, "ul.search_out.exp li")
                
                if not items:
                    print(f"행정안전부 페이지 {page}: 'ul.search_out.exp li' 선택자로 항목을 찾을 수 없음")
                    break
                
                print(f"행정안전부: {len(items)}개 항목 발견")
                
                page_items_count = 0
                for item in items:
                    try:
                        # 1. 첫 번째 p 태그에서 세목, 문서번호, 날짜 추출
                        first_p = item.find_element(By.TAG_NAME, "p")
                        
                        # 세목 추출 (span.part)
                        try:
                            tax_span = first_p.find_element(By.CSS_SELECTOR, "span.part")
                            tax_category = tax_span.text.strip()
                        except:
                            tax_category = ""
                        
                        # 첫 번째 p 태그의 전체 텍스트
                        first_p_text = first_p.text.strip()
                        
                        # 날짜 패턴 찾기 (2025.02.14)
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
                        
                        # 2. 두 번째 p.tt에서 제목 및 링크 추출
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
                            
                            # 첫 번째 유효 항목 로그
                            if page == 1 and page_items_count == 1:
                                print(f"첫 번째 유효 항목:")
                                print(f"  세목: '{tax_category}'")
                                print(f"  문서번호: '{doc_number}'")
                                print(f"  생산일자: '{date_part}'")
                                print(f"  제목: '{title[:50]}...'")
                                print(f"  링크: '{link}'")
                        
                    except Exception as e:
                        if page == 1:  # 첫 페이지에서만 오류 출력
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

# 테스트용 함수
if __name__ == "__main__":
    print("행정안전부 크롤러 테스트 (수정된 버전)...")
    result = crawl_mois_site_fixed(max_pages=1)
    print(f"결과: {len(result)}개 항목")
    if not result.empty:
        print("첫 번째 항목:")
        print(result.iloc[0])
        print("\n전체 데이터:")
        print(result)
    else:
        print("데이터 없음")