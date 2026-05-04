# 세금 관련 법령 크롤러 설정
#
# DEPRECATED NOTICE:
# URLS, DATA_COLUMNS, KEY_COLUMNS는 src/config/sites.py의
# SITE_CATALOG으로 이동되었습니다.
# 새 코드는 sites.py의 SITE_CATALOG, SITE_DISPLAY를 사용해주세요.
#
# 예: from src.config.sites import SITE_CATALOG, get_site
#     site = get_site("tax_tribunal")
#     url = site.url
#     key_column = site.key_column
#     data_columns = site.data_columns

# 기본 URL 설정 (DEPRECATED: SITE_CATALOG.url 사용)
BASE_URL = "https://www.tt.go.kr"
MOEF_URL = "https://www.moef.go.kr"

# 사이트별 URL 설정
URLS = {
    "tax_tribunal": BASE_URL,
    "nts_authority": "https://taxlaw.nts.go.kr/qt/USEQTJ001M.do",
    "nts_precedent": "https://taxlaw.nts.go.kr/pd/USEPDI001M.do",
    "moef": "https://www.moef.go.kr/lw/intrprt/TaxLawIntrPrtCaseList.do",
    "mois": "https://www.olta.re.kr/explainInfo/authoInterpretationList.do?menuNo=9020000&upperMenuId=9000000",
    "bai": "https://www.bai.go.kr/bai/exClaims/exClaims/list/",
    "scourt_major_decisions": "https://www.scourt.go.kr",
    "scourt_scheduled_decisions": "https://www.scourt.go.kr"
}

# 크롤링 설정
CRAWLING_CONFIG = {
    "max_pages": 20,
    "max_items": 5000,
    "retry_count": 3,
    "retry_delay": 5,
    "timeout": 30,  # 30초로 증가 (기존 10초)
    "max_load_attempts": 500,
    "selenium_timeout": 180,  # Selenium WebDriverWait 타임아웃 (3분)
    "page_load_timeout": 60   # 페이지 로드 타임아웃 (1분)
}

# 세목 리스트 (조세심판원)
SECTIONS = ["20", "11", "50", "12", "40", "95", "99"]

# 감사원 청구분야
BAI_CLAIM_TYPES = [
    {"value": "10", "name": "국세"},
    {"value": "20", "name": "지방세"}
]

# 파일 및 폴더 설정
FILE_CONFIG = {
    "data_folder": "data",
    "existing_file_template": "existing_data_{site_name}.xlsx",
    "updated_folder_template": "updated_cases/{site_name}"
}

# Selenium 설정
SELENIUM_OPTIONS = [
    "--headless",
    "--disable-gpu", 
    "--no-sandbox"
]

# 사이트별 데이터 컬럼 정의
DATA_COLUMNS = {
    "tax_tribunal": ["세목", "유형", "결정일", "청구번호", "제목", "링크"],
    "nts_authority": ["세목", "생산일자", "문서번호", "제목", "링크"],
    "nts_precedent": ["세목", "생산일자", "문서번호", "제목", "결론", "링크"],
    "moef": ["문서번호", "회신일자", "제목", "링크"],
    "mois": ["세목", "문서번호", "생산일자", "제목", "링크"],
    "bai": ["청구분야", "문서번호", "결정일자", "제목"],
    "scourt_major_decisions": ["번호", "작성일", "법원", "제목", "링크"],
    "scourt_scheduled_decisions": [
        "고유키", "선고일자", "재판부", "사건종류", "사건번호", "사건명",
        "조세관련", "관련키워드", "쟁점PDF", "보도자료링크"
    ]
}

# 사이트별 키 컬럼 정의
KEY_COLUMNS = {
    "tax_tribunal": "청구번호",
    "nts_authority": "문서번호",
    "nts_precedent": "문서번호", 
    "moef": "문서번호",
    "mois": "문서번호",
    "bai": "문서번호",
    "scourt_major_decisions": "번호",
    "scourt_scheduled_decisions": "고유키"
}

# GUI 설정
GUI_CONFIG = {
    "title": "자동 해석 탐색기",
    "site_options": [
        "1. 조세심판원",
        "2. 국세법령정보시스템 (유권해석)",
        "3. 기획재정부",
        "4. 국세법령정보시스템 (판례)",
        "5. 행정안전부",
        "6. 감사원",
        "7. 모두 크롤링",
        "8. 전국법원 주요판결",
        "9. 대법원 선고예정 판결"
    ],
    "default_interval": 60  # 기본 주기 (분)
}
