import os
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
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

# 설정
BASE_URL = "https://www.tt.go.kr"
MOEF_URL = "https://www.moef.go.kr"
SECTIONS = ["20", "11", "50", "12", "40", "95", "99"]  # 세목 리스트
MAX_PAGES = 20
DATA_FOLDER = "data"
EXISTING_FILE_TEMPLATE = "existing_data_{site_name}.xlsx"
UPDATED_FOLDER_TEMPLATE = "updated_cases/{site_name}"

# 재시도 로직
def safe_request(url, params, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # 상태 코드가 4xx, 5xx일 경우 예외 발생
            return response
        except (requests.exceptions.RequestException, TimeoutError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Exiting.")
                return None

# 기존 데이터 로드
def load_existing_data(site_name):
    existing_file = os.path.join(DATA_FOLDER, EXISTING_FILE_TEMPLATE.format(site_name=site_name))
    if os.path.exists(existing_file):
        if site_name == "심판원":
            return pd.read_excel(existing_file)
        elif site_name == "국세청":
            return pd.read_excel(existing_file)
        elif site_name == "기획재정부":
            return pd.read_excel(existing_file)
        elif site_name == "국세청_판례": # 국세청 판례 추가
            return pd.read_excel(existing_file)
        elif site_name == "행정안전부":
            return pd.read_excel(existing_file)
        elif site_name == "감사원":
            return pd.read_excel(existing_file)
    
    # 기본 열 구조 정의
    if site_name == "심판원":
        return pd.DataFrame(columns=["세목", "유형", "결정일", "청구번호", "제목", "링크"])
    elif site_name == "국세청":
        return pd.DataFrame(columns=["세목", "생산일자", "문서번호", "제목", "링크"])
    elif site_name == "기획재정부":
        return pd.DataFrame(columns=["문서번호", "회신일자", "제목", "링크"])
    elif site_name == "국세청_판례": # 국세청 판례 추가
        return pd.DataFrame(columns=["세목", "생산일자", "문서번호", "제목", "링크"])
    elif site_name == "행정안전부":
        return pd.DataFrame(columns=["세목", "문서번호", "생산일자", "제목", "링크"])
    elif site_name == "감사원":
        return pd.DataFrame(columns=["청구분야", "문서번호", "결정일자", "제목"])
    
    # 기본 반환 (예상치 못한 사이트 이름)
    return pd.DataFrame()

# 데이터 크롤링 (심판원) - 세목별로 진행 상태 업데이트
def crawl_data(site_name, section, max_pages, retries=3, delay=5, progress=None, status_message=None, current_section_index=0, total_sections=7):
    new_data = []
    total_cases = 0  # 크롤링된 총 사례 수
    cases_per_page = 0  # 페이지당 사례 수 (세목마다 다를 수 있음)
    
    # 첫 번째 페이지에서 사례 수를 확인하여 '페이지당 사례 수' 추정
    params = {"pageNumber": 1, "semok": section, "cbSearchOption": "subject", "cbJudge": "S500", "rdView": "subject"}
    response = safe_request(f"{BASE_URL}/mUser/dem/demList.do", params=params, retries=retries, delay=delay)
    
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        cases = soup.select(".result-box")
        cases_per_page = len(cases)  # 첫 페이지에서의 사례 수를 '페이지당 사례 수'로 설정
        
    total_estimated_cases = cases_per_page * max_pages  # 예상되는 총 사례 수

    for page in range(1, max_pages + 1):
        params = {"pageNumber": page, "semok": section, "cbSearchOption": "subject", "cbJudge": "S500", "rdView": "subject"}
        response = safe_request(f"{BASE_URL}/mUser/dem/demList.do", params=params, retries=retries, delay=delay)
        
        if not response:
            print(f"Failed to fetch page {page} for section {section} on site {site_name}. Skipping.")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        cases = soup.select(".result-box")
        for case in cases:
            tax_label = case.select_one("span.label-tax")
            type_label = case.select_one("span.label-decision")
            date_element = case.select_one("p.date")
            case_number = case.select_one("p.case-num")
            title_element = case.select_one("a")
            if not all([tax_label, type_label, date_element, case_number, title_element]):
                continue
            tax = tax_label.get_text(strip=True)
            case_type = type_label.get_text(strip=True)
            decision_date = date_element.get_text(strip=True).replace("결정일", "").strip()
            claim_number = case_number.get_text(strip=True).replace("청구번호", "").strip()
            title = title_element.get_text(strip=True)
            link = BASE_URL + title_element["href"] if title_element else ""
            new_data.append({
                "세목": tax,
                "유형": case_type,
                "결정일": decision_date,
                "청구번호": claim_number,
                "제목": title,
                "링크": link
            })
        
        total_cases += len(cases)  # 현재 페이지에서 크롤링된 사례 수를 추가
        
        # 진행 상태를 전체 예상 사례 수를 기준으로 업데이트
        if progress:
            progress['value'] = int((total_cases / total_estimated_cases) * 100)  # 사례 수 기준
            progress.update()  # 상태바 업데이트
        
        if status_message:
            status_message.config(text=f"세목 {current_section_index + 1}/{total_sections} 진행 중: {total_cases}/{total_estimated_cases} 사례")
        
    return pd.DataFrame(new_data)

# 최적화된 데이터 크롤링 (동적 사이트)
def crawl_dynamic_site(progress=None, status_message=None, max_items=5000):
    dynamic_url = "https://taxlaw.nts.go.kr/qt/USEQTJ001M.do"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(dynamic_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "more_show")))
        total_cases = 0
        max_load_attempts = 500
        current_attempt = 0
        
        # 1단계: 데이터 로딩
        if status_message:
            status_message.config(text="데이터 로딩 중...")
            status_message.update()
            
        while total_cases < max_items and current_attempt < max_load_attempts:
            try:
                current_attempt += 1
                cases = driver.find_elements(By.CSS_SELECTOR, "#bdltCtl > li")
                total_cases = len(cases)
                
                if total_cases >= max_items:
                    break
                    
                try:
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "more_show"))
                    )
                    driver.execute_script("arguments[0].click();", load_more_button)
                    
                    if current_attempt % 5 == 0 and status_message:  # 5번에 한 번씩만 UI 업데이트
                        status_message.config(text=f"데이터 로딩 중: {total_cases}/{max_items} 사례")
                        status_message.update()
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"더 이상 항목을 로드할 수 없습니다: {e}")
                    break
            except Exception as e:
                print(f"데이터 로드 중 오류 발생: {e}")
                time.sleep(2)
        
        # 2단계: 최적화된 데이터 추출 및 처리
        if status_message:
            status_message.config(text=f"데이터 처리 중... (총 {total_cases}개 항목)")
            status_message.update()
        
        # 자바스크립트를 사용하여 한 번에 모든 필요한 데이터 추출
        js_script = """
        const items = document.querySelectorAll("#bdltCtl > li");
        
        // 실제 DOM 구조 분석
        console.log("=== DOM 구조 분석 ===");
        
        // 첫 번째 항목의 구조 분석
        const firstItem = items[0];
        if (firstItem) {
            const clickableElement = firstItem.querySelector("a.subs_title");
            if (clickableElement) {
                console.log("첫 번째 항목 링크 분석:");
                console.log("  href:", clickableElement.getAttribute("href"));
                console.log("  onclick:", clickableElement.getAttribute("onclick"));
                console.log("  모든 속성:", Array.from(clickableElement.attributes).map(attr => attr.name + "=" + attr.value));
                console.log("  HTML:", clickableElement.outerHTML.substring(0, 200));
            }
        }
        
        // nav 요소들 확인 (다양한 선택자로)
        const navElements1 = document.querySelectorAll("nav [data-ntstdcmid]");
        const navElements2 = document.querySelectorAll("[data-ntstdcmid]");
        const navElements3 = document.querySelectorAll("nav");
        console.log("nav [data-ntstdcmid] 요소 개수:", navElements1.length);
        console.log("[data-ntstdcmid] 요소 개수:", navElements2.length);
        console.log("nav 요소 개수:", navElements3.length);
        
        if (navElements2.length > 0) {
            console.log("data-ntstdcmid 샘플:", Array.from(navElements2).slice(0, 3).map(el => ({
                tagName: el.tagName,
                id: el.getAttribute("data-ntstdcmid"),
                text: el.textContent.trim().substring(0, 50)
            })));
        }
        
        const navElements = navElements1;
        
        const navMap = new Map();
        navElements.forEach((navEl, index) => {
            const navTitle = navEl.textContent.trim();
            const ntstDcmId = navEl.getAttribute("data-ntstdcmid");
            if (navTitle && ntstDcmId) {
                navMap.set(navTitle, ntstDcmId);
                if (index < 3) console.log("nav 샘플:", navTitle, "->", ntstDcmId);
            }
        });
        
        let debugInfo = {
            navElementsCount: navElements.length,
            navMapSize: navMap.size,
            linkFoundCount: 0,
            onclickFoundCount: 0,
            samples: []
        };
        
        const result = Array.from(items).map((item, index) => {
            try {
                const taxLabel = item.querySelector("ul.legislation_list li:nth-child(2)").getAttribute("title").trim();
                const productionDate = item.querySelector("ul.subs_detail li span.num").textContent.trim();
                const docNumber = item.querySelector("ul.subs_detail li strong").textContent.trim();
                const title = item.querySelector("a.subs_title strong").textContent.trim();
                
                // ntstDcmId 추출 시도 (유권해석용)
                let ntstDcmId = "";
                let link = "";
                let foundMethod = "";
                
                // 방법 1: 항목의 클릭 이벤트나 데이터 속성에서 찾기
                const clickableElement = item.querySelector("a.subs_title");
                if (clickableElement) {
                    const onclickAttr = clickableElement.getAttribute("onclick");
                    if (onclickAttr) {
                        debugInfo.onclickFoundCount++;
                        if (index < 3) debugInfo.samples.push({onclick: onclickAttr});
                        
                        if (onclickAttr.includes("ntstDcmId")) {
                            const match = onclickAttr.match(/ntstDcmId['"]\s*:\s*['"]([^'"]+)['"]/);
                            if (match) {
                                ntstDcmId = match[1];
                                foundMethod = "onclick";
                            }
                        }
                    }
                }
                
                // 방법 2: 미리 구성한 Map에서 제목으로 매칭
                if (!ntstDcmId && navMap.has(title)) {
                    ntstDcmId = navMap.get(title);
                    foundMethod = "navMap";
                }
                
                // 링크 생성 (유권해석 URL 형태)
                if (ntstDcmId) {
                    link = `https://taxlaw.nts.go.kr/qt/USEQTA002P.do?ntstDcmId=${ntstDcmId}&wnkey=94b6d019-af7d-4f9c-9863-8b183e27c1ff`;
                    debugInfo.linkFoundCount++;
                    if (index < 3) debugInfo.samples.push({title, ntstDcmId, foundMethod});
                }
                
                return {taxLabel, productionDate, docNumber, title, link};
            } catch (e) {
                return {error: e.toString()};
            }
        });
        
        console.log("디버그 정보:", debugInfo);
        return {data: result, debug: debugInfo};
        """
        
        # 자바스크립트 실행으로 데이터 한 번에 추출
        js_result = driver.execute_script(js_script)
        raw_items = js_result['data']
        debug_info = js_result['debug']
        
        # 디버그 정보 출력
        print(f"디버그 정보:")
        print(f"  nav 요소 개수: {debug_info['navElementsCount']}")
        print(f"  nav Map 크기: {debug_info['navMapSize']}")
        print(f"  onclick 속성 발견 개수: {debug_info['onclickFoundCount']}")
        print(f"  링크 생성 개수: {debug_info['linkFoundCount']}")
        if debug_info['samples']:
            print(f"  샘플 데이터: {debug_info['samples'][:3]}")
        
        # 중복 제거 및 유효한 항목만 필터링 (파이썬 측에서 빠르게 처리)
        data = []
        doc_numbers_set = set()
        valid_items_count = 0
        
        for idx, item in enumerate(raw_items):
            if 'error' in item:
                continue
                
            doc_number = item['docNumber']
            if doc_number not in doc_numbers_set:
                doc_numbers_set.add(doc_number)
                data.append({
                    "세목": item['taxLabel'],
                    "생산일자": item['productionDate'],
                    "문서번호": doc_number,
                    "제목": item['title'],
                    "링크": item.get('link', '')
                })
                valid_items_count += 1
            
            # 진행률 업데이트 (10% 단위로만)
            if progress and idx % (max(1, len(raw_items) // 10)) == 0:
                progress['value'] = int((idx / len(raw_items)) * 100)
                progress.update()
        
        if progress:
            progress['value'] = 100
            progress.update()

        if status_message:
            status_message.config(text=f"크롤링 완료: 총 {valid_items_count}개 사례 수집 (중복 {total_cases - valid_items_count}개 제외)")
        
        print(f"총 {total_cases}개 항목 중 {valid_items_count}개 고유 항목 수집 완료 (중복 {total_cases - valid_items_count}개 제외)")
        
        return pd.DataFrame(data, columns=["세목", "생산일자", "문서번호", "제목", "링크"])

    finally:
        driver.quit()

# 국세청 판례 크롤링 함수 (crawl_dynamic_site 기반)
def crawl_nts_precedents(progress=None, status_message=None, max_items=5000):
    dynamic_url = "https://taxlaw.nts.go.kr/pd/USEPDI001M.do"  # 판례 URL로 변경
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(dynamic_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "more_show")))
        total_cases = 0
        max_load_attempts = 500  # 기존 crawl_dynamic_site와 동일하게 설정
        current_attempt = 0
        
        # 1단계: 데이터 로딩
        if status_message:
            status_message.config(text="국세청 판례 데이터 로딩 중...")
            status_message.update()
            
        while total_cases < max_items and current_attempt < max_load_attempts:
            try:
                current_attempt += 1
                cases = driver.find_elements(By.CSS_SELECTOR, "#bdltCtl > li")
                total_cases = len(cases)
                
                if total_cases >= max_items:
                    break
                    
                try:
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "more_show"))
                    )
                    driver.execute_script("arguments[0].click();", load_more_button)
                    
                    if current_attempt % 5 == 0 and status_message:
                        status_message.config(text=f"국세청 판례 데이터 로딩 중: {total_cases}/{max_items} 사례")
                        status_message.update()
                    
                    time.sleep(1) # 페이지 로드 대기
                except Exception as e:
                    print(f"더 이상 국세청 판례 항목을 로드할 수 없습니다: {e}")
                    break
            except Exception as e:
                print(f"국세청 판례 데이터 로드 중 오류 발생: {e}")
                time.sleep(2)
        
        # 2단계: 최적화된 데이터 추출 및 처리
        if status_message:
            status_message.config(text=f"국세청 판례 데이터 처리 중... (총 {total_cases}개 항목)")
            status_message.update()
        
        js_script = """
        const items = document.querySelectorAll("#bdltCtl > li");
        return Array.from(items).map(item => {
            try {
                const taxLabelElement = item.querySelector("ul.legislation_list li:nth-child(2)");
                const taxLabel = taxLabelElement ? taxLabelElement.getAttribute("title").trim() : ""; // 세목
                const productionDateElement = item.querySelector("ul.subs_detail li span.num");
                const productionDate = productionDateElement ? productionDateElement.textContent.trim() : ""; // 생산일자 (선고일자)
                const docNumberElement = item.querySelector("ul.subs_detail li strong");
                const docNumber = docNumberElement ? docNumberElement.textContent.trim() : ""; // 문서번호 (사건번호)
                const titleElement = item.querySelector("a.subs_title strong");
                const title = titleElement ? titleElement.textContent.trim() : ""; // 제목
                
                // ntstDcmId 추출 시도 (여러 방법)
                let ntstDcmId = "";
                let link = "";
                
                // 방법 1: 항목의 클릭 이벤트나 데이터 속성에서 찾기
                const clickableElement = item.querySelector("a.subs_title");
                if (clickableElement) {
                    // onclick 속성이나 데이터 속성 확인
                    const onclickAttr = clickableElement.getAttribute("onclick");
                    if (onclickAttr && onclickAttr.includes("ntstDcmId")) {
                        const match = onclickAttr.match(/ntstDcmId['"]\s*:\s*['"]([^'"]+)['"]/);
                        if (match) ntstDcmId = match[1];
                    }
                }
                
                // 방법 2: 네비게이션에서 제목으로 매칭
                if (!ntstDcmId) {
                    const navElements = document.querySelectorAll("nav [data-ntstdcmid]");
                    for (let navEl of navElements) {
                        const navTitle = navEl.textContent.trim();
                        if (navTitle === title) {
                            ntstDcmId = navEl.getAttribute("data-ntstdcmid");
                            break;
                        }
                    }
                }
                
                // 방법 3: 전역 변수나 함수에서 현재 페이지의 ntstDcmId 목록 확인
                if (!ntstDcmId && typeof window.currentPageData !== 'undefined') {
                    // 페이지에 데이터가 있다면 활용
                }
                
                // 링크 생성
                if (ntstDcmId) {
                    link = `https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=${ntstDcmId}&wnkey=f3fe8963-8e4b-4831-b9e6-59ec0ebe328c`;
                }
                
                return {taxLabel, productionDate, docNumber, title, link};
            } catch (e) {
                return {error: e.toString()};
            }
        });
        """
        
        raw_items = driver.execute_script(js_script)
        
        data = []
        doc_numbers_set = set()
        valid_items_count = 0
        
        for idx, item in enumerate(raw_items):
            if 'error' in item or not item.get('docNumber'): # 문서번호가 없는 경우 제외
                continue
                
            doc_number = item['docNumber']
            if doc_number not in doc_numbers_set:
                doc_numbers_set.add(doc_number)
                data.append({
                    "세목": item['taxLabel'],
                    "생산일자": item['productionDate'],
                    "문서번호": doc_number,
                    "제목": item['title'],
                    "링크": item.get('link', '')
                })
                valid_items_count += 1
            
            if progress and idx % (max(1, len(raw_items) // 10)) == 0:
                progress['value'] = int((idx / len(raw_items)) * 100)
                progress.update()
        
        if progress:
            progress['value'] = 100
            progress.update()

        if status_message:
            status_message.config(text=f"국세청 판례 크롤링 완료: 총 {valid_items_count}개 사례 수집 (중복 {total_cases - valid_items_count}개 제외)")
        
        print(f"국세청 판례: 총 {total_cases}개 항목 중 {valid_items_count}개 고유 항목 수집 완료 (중복 {total_cases - valid_items_count}개 제외)")
        
        return pd.DataFrame(data, columns=["세목", "생산일자", "문서번호", "제목", "링크"])

    finally:
        driver.quit()

# 행정안전부 유권해석 크롤링 함수 추가 (Selenium 사용)
def crawl_mois_site(progress=None, status_message=None, max_pages=10):
    mois_url = "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(mois_url)
        
        if status_message:
            status_message.config(text="행정안전부 데이터 로딩 중...")
            status_message.update()
        
        # 페이지 로딩 대기
        time.sleep(5)
        
        all_items = []
        page = 1
        
        while page <= max_pages:
            try:
                if status_message:
                    status_message.config(text=f"행정안전부 페이지 {page}/{max_pages} 크롤링 중...")
                    status_message.update()
                
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
                
                print(f"행정안전부: 'ul.search_out.exp li' 선택자로 {len(items)}개 항목 발견")
                
                page_items_count = 0
                for item in items:
                    try:
                        # HTML 구조에 따른 정확한 데이터 추출
                        # <p><span class="part">취득세</span>부동산세제과-1201 (2025.04.23)</p>
                        # <p class="tt"><a>제목</a></p>
                        
                        # 세목과 문서번호, 날짜가 있는 첫 번째 p 태그
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
                                # authoritativePopUp(60096503) 에서 60096503 추출
                                import re
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
                    progress['value'] = int((page / max_pages) * 100)
                    progress.update()
                    
            except Exception as e:
                print(f"행정안전부 페이지 {page} 처리 중 오류: {e}")
                break
        
        if status_message:
            status_message.config(text=f"행정안전부 크롤링 완료: 총 {len(all_items)}개 항목 수집")
        
        print(f"행정안전부: 총 {len(all_items)}개 항목 수집 완료")
        
        return pd.DataFrame(all_items, columns=["세목", "문서번호", "생산일자", "제목", "링크"])

    finally:
        driver.quit()

# 감사원 심사결정례 크롤링 함수 추가 (청구분야별)
def crawl_bai_site(progress=None, status_message=None, max_pages=20):
    bai_url = "https://www.bai.go.kr/bai/exClaims/exClaims/list/"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    
    # 청구분야 목록 (조세 관련만)
    claim_types = [
        {"value": "10", "name": "국세"},
        {"value": "20", "name": "지방세"}
    ]
    
    try:
        all_data = []
        
        for claim_type in claim_types:
            if status_message:
                status_message.config(text=f"감사원 {claim_type['name']} 데이터 로딩 중...")
                status_message.update()
            
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
            
            # 청구분야가 포함된 URL로 직접 이동하는 방식 시도
            try:
                # 청구분야별 URL 파라미터로 직접 접근
                search_url = f"{bai_url}?reqDvsnCd={claim_type['value']}"
                driver.get(search_url)
                print(f"청구분야 '{claim_type['name']}' URL로 직접 이동: {search_url}")
                time.sleep(5)
                
                # 또는 드롭다운 선택 방식
                try:
                    select_element = driver.find_element(By.CSS_SELECTOR, "select#reqDvsnCd")
                    from selenium.webdriver.support.ui import Select
                    select = Select(select_element)
                    select.select_by_value(claim_type["value"])
                    print(f"청구분야 '{claim_type['name']}' 드롭다운 선택 완료")
                    time.sleep(1)
                    
                    # searchForm 내부의 검색 버튼 클릭 (정확한 타겟)
                    try:
                        search_button = driver.find_element(By.CSS_SELECTOR, "div.searchForm button[type='button']")
                        driver.execute_script("arguments[0].click();", search_button)
                        print("searchForm 내부 검색 버튼 클릭 완료")
                        search_clicked = True
                    except Exception as e:
                        print(f"searchForm 검색 버튼 클릭 실패: {e}")
                        search_clicked = False
                    
                    if not search_clicked:
                        print("검색 버튼을 찾을 수 없음, URL 파라미터 방식으로 진행")
                    
                    time.sleep(3)
                    
                    # 검색 후 URL 확인
                    current_url = driver.current_url
                    print(f"검색 후 현재 URL: {current_url}")
                    
                    # 만약 통합검색 페이지로 이동했다면 다시 원래 페이지로 돌아가기
                    if "konan" in current_url or "search" in current_url:
                        print("통합검색 페이지로 이동함, 원래 페이지로 복귀")
                        original_url = f"{bai_url}?reqDvsnCd={claim_type['value']}"
                        driver.get(original_url)
                        time.sleep(3)
                    
                except Exception as dropdown_error:
                    print(f"드롭다운 선택 실패: {dropdown_error}, URL 파라미터 방식으로 진행")
                
            except Exception as e:
                print(f"청구분야 '{claim_type['name']}' 접근 실패: {e}")
                continue
            
            # 해당 분야에서 페이지별 데이터 수집
            page = 1
            pages_per_type = 10  # 각 분야별로 10페이지씩
            
            while page <= pages_per_type:
                try:
                    if status_message:
                        status_message.config(text=f"감사원 {claim_type['name']} 페이지 {page}/{pages_per_type} 크롤링 중...")
                        status_message.update()
                    
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
                        # 디버깅을 위해 페이지 소스 일부 출력
                        print("현재 페이지 URL:", driver.current_url)
                        page_source = driver.page_source[:2000]
                        print("페이지 소스 샘플:")
                        print(page_source)
                        break
                    
                    page_data_count = 0
                    for item in items:
                        try:
                            cells = item.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 4:  # 최소 4개 열 필요
                                # 첫 번째 항목에서 테이블 구조 분석
                                if page == 1 and page_data_count == 0:
                                    print(f"감사원 테이블 구조 분석 (총 {len(cells)}개 열):")
                                    for i, cell in enumerate(cells):
                                        cell_text = cell.text.strip()
                                        print(f"  열 {i}: '{cell_text}'")
                                
                                # 정확한 테이블 구조에 따른 데이터 추출
                                # 열 0: 결정번호 (2025-심사-271)
                                # 열 1: 결정일자 (2025-06-13)  
                                # 열 2: 구분 (심사)
                                # 열 3: 제목
                                # 열 4: 첨부파일 (있는 경우)
                                
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
                                    
                                    # 첫 번째 유효한 항목 로그 (각 분야별로)
                                    if page == 1 and page_data_count == 1:
                                        print(f"{claim_type['name']} 분야 첫 번째 유효 항목:")
                                        print(f"  문서번호: '{doc_number}'")
                                        print(f"  결정일자: '{decision_date}'")
                                        print(f"  구분: '{category}'")
                                        print(f"  제목: '{title[:50]}...'")
                                else:
                                    # 디버깅을 위해 유효하지 않은 항목 정보 출력
                                    if page == 1 and page_data_count < 3:
                                        print(f"{claim_type['name']} 무효 항목 (결정번호: '{doc_number}', 제목: '{title[:30]}...')")
                                        
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
                            # Vue.js 동적 사이트에서 페이지 번호 링크 클릭
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
                progress['value'] = int(current_progress)
                progress.update()
        
        if status_message:
            status_message.config(text=f"감사원 크롤링 완료: 총 {len(all_data)}개 사례 수집")
        
        print(f"감사원 전체 크롤링 완료:")
        for claim_type in claim_types:
            type_count = len([item for item in all_data if item.get('청구분야') == claim_type['name']])
            print(f"  {claim_type['name']}: {type_count}개")
        print(f"  전체: {len(all_data)}개 항목")
        
        return pd.DataFrame(all_data, columns=["청구분야", "문서번호", "결정일자", "제목"])

    finally:
        driver.quit()

# 기획재정부 사이트 크롤링 함수 추가
def crawl_moef_site(progress=None, status_message=None, max_pages=10):
    moef_url_template = "https://www.moef.go.kr/lw/intrprt/TaxLawIntrPrtCaseList.do?bbsId=MOSFBBS_000000000237&menuNo=8120300&pageIndex={page}"
    all_items = []
    total_items = 0
    items_per_page = 10  # 페이지당 예상 항목 수
    
    if status_message:
        status_message.config(text="기획재정부 데이터 크롤링 중...")
        status_message.update()
    
    # 예상 총 항목 수 계산
    total_estimated_items = items_per_page * max_pages
    
    for page in range(1, max_pages + 1):
        if status_message:
            status_message.config(text=f"기획재정부 페이지 {page}/{max_pages} 크롤링 중...")
            status_message.update()
        
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
            progress['value'] = int((total_items / total_estimated_items) * 100)
            progress.update()
    
    if status_message:
        status_message.config(text=f"기획재정부 크롤링 완료: 총 {total_items}개 항목 수집")
        
    return pd.DataFrame(all_items)

# 새로운 데이터와 기존 데이터 비교
def compare_data(existing_data, new_data, key_column):
    if key_column not in existing_data.columns or key_column not in new_data.columns:
        raise KeyError(f"Both datasets must contain '{key_column}' column to compare data.")
    
    # 디버깅 정보
    print(f"[DEBUG] compare_data:")
    print(f"  기존 데이터: {len(existing_data)}개")
    print(f"  새 데이터: {len(new_data)}개")
    
    existing_keys = set(existing_data[key_column].astype(str))
    new_keys = set(new_data[key_column].astype(str))
    
    print(f"  기존 키 개수: {len(existing_keys)}")
    print(f"  새 키 개수: {len(new_keys)}")
    print(f"  기존 키 샘플: {list(existing_keys)[:3]}")
    print(f"  새 키 샘플: {list(new_keys)[:3]}")
    
    # 차집합 계산
    new_only = new_keys - existing_keys
    existing_only = existing_keys - new_keys
    common = existing_keys & new_keys
    
    print(f"  새 데이터에만 있는 키: {len(new_only)}개")
    print(f"  기존 데이터에만 있는 키: {len(existing_only)}개") 
    print(f"  공통 키: {len(common)}개")
    
    if len(new_only) > 0:
        print(f"  새 키 샘플: {list(new_only)[:5]}")
    if len(existing_only) > 0:
        print(f"  기존 전용 키 샘플: {list(existing_only)[:5]}")
    
    # 원래 로직
    new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
    print(f"  최종 새 항목: {len(new_entries)}개")
    
    return new_entries

# 업데이트된 데이터를 저장 및 기존 데이터 업데이트
def save_updated_data(site_name, updated_data):
    if not updated_data.empty:
        updated_folder = UPDATED_FOLDER_TEMPLATE.format(site_name=site_name)
        if not os.path.exists(updated_folder):
            os.makedirs(updated_folder)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        updated_file = os.path.join(updated_folder, f"updated_cases_{timestamp}.xlsx")
        updated_data.to_excel(updated_file, index=False)
        print(f"업데이트된 사례가 {updated_file}에 저장되었습니다.")

# 기존 데이터에 새 데이터를 추가하는 방식으로 수정
def update_existing_data(site_name, new_data):
    if site_name == "심판원":
        key_column = "청구번호"
    elif site_name == "국세청_판례": # 국세청 판례 키 컬럼
        key_column = "문서번호"
    elif site_name == "감사원":
        key_column = "문서번호"
    else: # 국세청, 기획재정부, 행정안전부
        key_column = "문서번호"
        
    existing_file = os.path.join(DATA_FOLDER, EXISTING_FILE_TEMPLATE.format(site_name=site_name))
    
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    
    if os.path.exists(existing_file):
        # 기존 데이터 로드
        existing_data = pd.read_excel(existing_file)
        
        # 기존 데이터와 새 데이터에서 중복되지 않는 항목만 추가
        new_entries = new_data[~new_data[key_column].isin(existing_data[key_column])]
        
        # 기존 데이터와 새 데이터 병합
        updated_data = pd.concat([existing_data, new_entries], ignore_index=True)
    else:
        # 기존 파일이 없는 경우 새 데이터를 그대로 사용
        updated_data = new_data
    
    # 병합된 데이터 저장
    updated_data.to_excel(existing_file, index=False)
    print(f"기존 데이터에 새 데이터가 추가되어 {existing_file}에 저장되었습니다.")

# UI 업데이트 및 메시지 표시
def show_message(message):
    messagebox.showinfo("크롤링 완료", message)

# 메인 로직 (UI 포함) - 주기적인 크롤링 추가
def main_ui():
    def on_crawl_click():
        choice = site_choice.get().split(".")[0].strip()  # 선택된 값에서 번호만 추출
        progress['value'] = 0  # 진행 상태 초기화
        progress.update()  # 상태바 초기화
        
        summary_messages = []

        # 심판원 크롤링
        if choice == "1" or choice == "7":
            site_name = "심판원"
            msg = ""
            existing_data = load_existing_data(site_name)
            all_new_data = []
            total_sections = len(SECTIONS)
            for idx, section in enumerate(SECTIONS):
                section_data = crawl_data(site_name, section, MAX_PAGES, progress=progress, status_message=status_message, current_section_index=idx, total_sections=total_sections)
                all_new_data.append(section_data)
            if all_new_data:
                new_data = pd.concat(all_new_data, ignore_index=True)
                if not new_data.empty:
                    new_entries = compare_data(existing_data, new_data, key_column="청구번호")
                    if not new_entries.empty:
                        save_updated_data(site_name, new_entries)
                        update_existing_data(site_name, new_data)
                        msg = f"심판원: 새로운 심판례 {len(new_entries)} 개 발견."
                    else:
                        msg = "심판원: 새로운 심판례 없음."
                else:
                    msg = "심판원: 크롤링 결과 데이터 없음."
            else:
                msg = "심판원: 크롤링 중 오류 또는 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)

        # 국세청 유권해석 크롤링
        if choice == "2" or choice == "7":
            site_name = "국세청"
            msg = ""
            dynamic_data = crawl_dynamic_site(progress=progress, status_message=status_message, max_items=5000)
            existing_data = load_existing_data(site_name)
            if not dynamic_data.empty:
                new_entries = compare_data(existing_data, dynamic_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, dynamic_data)
                    msg = f"국세청 유권해석: 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    msg = "국세청 유권해석: 새로운 유권해석 없음."
            else:
                msg = "국세청 유권해석: 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)
                
        # 기획재정부 크롤링
        if choice == "3" or choice == "7":
            site_name = "기획재정부"
            msg = ""
            moef_data = crawl_moef_site(progress=progress, status_message=status_message, max_pages=10)
            existing_data = load_existing_data(site_name)
            if not moef_data.empty:
                new_entries = compare_data(existing_data, moef_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, moef_data)
                    msg = f"기획재정부: 새로운 해석 {len(new_entries)} 개 발견."
                else:
                    msg = "기획재정부: 새로운 해석 없음."
            else:
                msg = "기획재정부: 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)

        # 국세청 판례 크롤링
        if choice == "4" or choice == "7":
            site_name = "국세청_판례"
            msg = ""
            nts_precedent_data = crawl_nts_precedents(progress=progress, status_message=status_message, max_items=5000)
            existing_data = load_existing_data(site_name)
            if not nts_precedent_data.empty:
                new_entries = compare_data(existing_data, nts_precedent_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, nts_precedent_data)
                    msg = f"국세청 판례: 새로운 판례 {len(new_entries)} 개 발견."
                else:
                    msg = "국세청 판례: 새로운 판례 없음."
            else:
                msg = "국세청 판례: 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)

        # 행정안전부 유권해석 크롤링
        if choice == "5" or choice == "7":
            site_name = "행정안전부"
            msg = ""
            existing_data = load_existing_data(site_name)
            mois_data = crawl_mois_site(progress=progress, status_message=status_message, max_pages=10)
            if not mois_data.empty:
                new_entries = compare_data(existing_data, mois_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, mois_data)
                    msg = f"행정안전부: 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    msg = "행정안전부: 새로운 유권해석 없음."
            else:
                msg = "행정안전부: 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)

        # 감사원 심사결정례 크롤링
        if choice == "6" or choice == "7":
            site_name = "감사원"
            msg = ""
            existing_data = load_existing_data(site_name)
            bai_data = crawl_bai_site(progress=progress, status_message=status_message, max_pages=20)
            if not bai_data.empty:
                new_entries = compare_data(existing_data, bai_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, bai_data)
                    msg = f"감사원: 새로운 심사결정례 {len(new_entries)} 개 발견."
                else:
                    msg = "감사원: 새로운 심사결정례 없음."
            else:
                msg = "감사원: 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages.append(msg)
            else:
                show_message(msg)
        
        if choice == "7":
            if summary_messages:
                show_message("\n".join(summary_messages))
            else: # 이 경우는 choice가 7인데 아무것도 실행 안됐을 때 (이론상 발생 안함)
                show_message("모두 크롤링: 처리된 항목이 없습니다.")
        elif choice not in ["1", "2", "3", "4", "5", "6"]: # 7이 아닌 잘못된 선택
            show_message("잘못된 선택입니다. 유효한 옵션을 선택해 주세요.")

    # 주기적인 크롤링을 위한 함수 추가
    def periodic_crawl():
        choice = site_choice.get().split(".")[0].strip()  # 선택된 사이트 번호 가져오기
        
        summary_messages_periodic = []

        # 심판원 크롤링
        if choice == "1" or choice == "7":
            site_name = "심판원"
            msg = ""
            existing_data = load_existing_data(site_name)
            all_new_data = []
            total_sections = len(SECTIONS)
            for idx, section in enumerate(SECTIONS):
                section_data = crawl_data(site_name, section, MAX_PAGES, progress=progress, status_message=status_message, current_section_index=idx, total_sections=total_sections)
                all_new_data.append(section_data)
            if all_new_data:
                new_data = pd.concat(all_new_data, ignore_index=True)
                if not new_data.empty:
                    new_entries = compare_data(existing_data, new_data, key_column="청구번호")
                    if not new_entries.empty:
                        save_updated_data(site_name, new_entries)
                        update_existing_data(site_name, new_data)
                        msg = f"주기적 크롤링 (심판원): 새로운 심판례 {len(new_entries)} 개 발견."
                    else:
                        msg = "주기적 크롤링 (심판원): 새로운 심판례 없음."
                else:
                    msg = "주기적 크롤링 (심판원): 크롤링 결과 데이터 없음."
            else:
                msg = "주기적 크롤링 (심판원): 크롤링 중 오류 또는 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)

        # 국세청 유권해석 크롤링
        if choice == "2" or choice == "7":
            site_name = "국세청"
            msg = ""
            dynamic_data = crawl_dynamic_site(progress=progress, status_message=status_message, max_items=5000)
            existing_data = load_existing_data(site_name)
            if not dynamic_data.empty:
                new_entries = compare_data(existing_data, dynamic_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, dynamic_data)
                    msg = f"주기적 크롤링 (국세청 유권해석): 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    msg = "주기적 크롤링 (국세청 유권해석): 새로운 유권해석 없음."
            else:
                msg = "주기적 크롤링 (국세청 유권해석): 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)
                
        # 기획재정부 크롤링
        if choice == "3" or choice == "7":
            site_name = "기획재정부"
            msg = ""
            moef_data = crawl_moef_site(progress=progress, status_message=status_message, max_pages=10)
            existing_data = load_existing_data(site_name)
            if not moef_data.empty:
                new_entries = compare_data(existing_data, moef_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, moef_data)
                    msg = f"주기적 크롤링 (기획재정부): 새로운 해석 {len(new_entries)} 개 발견."
                else:
                    msg = "주기적 크롤링 (기획재정부): 새로운 해석 없음."
            else:
                msg = "주기적 크롤링 (기획재정부): 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)

        # 국세청 판례 크롤링
        if choice == "4" or choice == "7":
            site_name = "국세청_판례"
            msg = ""
            nts_precedent_data = crawl_nts_precedents(progress=progress, status_message=status_message, max_items=5000)
            existing_data = load_existing_data(site_name)
            if not nts_precedent_data.empty:
                new_entries = compare_data(existing_data, nts_precedent_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, nts_precedent_data)
                    msg = f"주기적 크롤링 (국세청 판례): 새로운 판례 {len(new_entries)} 개 발견."
                else:
                    msg = "주기적 크롤링 (국세청 판례): 새로운 판례 없음."
            else:
                msg = "주기적 크롤링 (국세청 판례): 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)

        # 행정안전부 유권해석 크롤링
        if choice == "5" or choice == "7":
            site_name = "행정안전부"
            msg = ""
            existing_data = load_existing_data(site_name)
            mois_data = crawl_mois_site(progress=progress, status_message=status_message, max_pages=10)
            if not mois_data.empty:
                new_entries = compare_data(existing_data, mois_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, mois_data)
                    msg = f"주기적 크롤링 (행정안전부): 새로운 유권해석 {len(new_entries)} 개 발견."
                else:
                    msg = "주기적 크롤링 (행정안전부): 새로운 유권해석 없음."
            else:
                msg = "주기적 크롤링 (행정안전부): 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)

        # 감사원 심사결정례 크롤링
        if choice == "6" or choice == "7":
            site_name = "감사원"
            msg = ""
            existing_data = load_existing_data(site_name)
            bai_data = crawl_bai_site(progress=progress, status_message=status_message, max_pages=20)
            if not bai_data.empty:
                new_entries = compare_data(existing_data, bai_data, key_column="문서번호")
                if not new_entries.empty:
                    save_updated_data(site_name, new_entries)
                    update_existing_data(site_name, bai_data)
                    msg = f"주기적 크롤링 (감사원): 새로운 심사결정례 {len(new_entries)} 개 발견."
                else:
                    msg = "주기적 크롤링 (감사원): 새로운 심사결정례 없음."
            else:
                msg = "주기적 크롤링 (감사원): 크롤링 결과 데이터 없음."
            if choice == "7":
                summary_messages_periodic.append(msg)
            else:
                show_message(msg)

        if choice == "7":
            if summary_messages_periodic:
                show_message("주기적 크롤링 결과:\n" + "\n".join(summary_messages_periodic))
            else: # 이 경우는 choice가 7인데 아무것도 실행 안됐을 때
                show_message("주기적 크롤링: 처리된 항목이 없습니다.")
        
        # 주어진 시간(분) 후 다시 실행
        interval_str = time_entry.get()
        if interval_str.isdigit():
            interval = int(interval_str) * 60000  # 입력된 시간(분)을 밀리초로 변환
        else:
            show_message("주기 입력 오류: 숫자를 입력해주세요. 기본값 60분으로 재시도합니다.")
            interval = 60 * 60000 # 기본값 60분
        window.after(interval, periodic_crawl)  # 다시 실행


    # UI 구성
    window = tk.Tk()
    window.title("자동 해석 탐색기")

    label = tk.Label(window, text="사이트를 선택하세요:")
    label.pack(pady=10)

    site_choice = ttk.Combobox(window, values=[
        "1. 조세심판원",
        "2. 국세법령정보시스템 (유권해석)",
        "3. 기획재정부",
        "4. 국세법령정보시스템 (판례)",
        "5. 행정안전부",
        "6. 감사원",
        "7. 모두 크롤링"
    ])
    site_choice.pack(pady=10)

    crawl_button = tk.Button(window, text="시작", command=on_crawl_click)
    crawl_button.pack(pady=20)

    # 상태 메시지 추가
    status_message = tk.Label(window, text="진행 상태")
    status_message.pack(pady=5)

    # 진행 상태바 추가
    progress = ttk.Progressbar(window, length=300, mode="determinate", maximum=100)
    progress.pack(pady=10)

    # 주기적인 크롤링을 위한 시간 입력 필드 (분)
    time_label = tk.Label(window, text="주기 (분):")
    time_label.pack(pady=5)
    time_entry = tk.Entry(window)
    time_entry.pack(pady=5)
    time_entry.insert(0, "60")  # 기본값: 60분

    # 주기적인 크롤링 시작 버튼
    periodic_button = tk.Button(window, text="자동 탐색 시작", command=periodic_crawl)
    periodic_button.pack(pady=20)

    window.mainloop()

if __name__ == "__main__":
    main_ui()