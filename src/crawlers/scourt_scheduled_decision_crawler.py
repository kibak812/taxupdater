"""
대법원 선고예정 판결 크롤러

목록 페이지가 서버 렌더링 HTML을 제공하므로 Selenium 없이 requests와
BeautifulSoup만 사용합니다. v1에서는 PDF 본문 분석 없이 사건명 단계에서
조세 관련 후보를 판정합니다.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config.sites import SCOURT_NON_TAX_STATUS, get_site
from src.crawlers.base_crawler import BaseCrawler


class ScourtScheduledDecisionCrawler(BaseCrawler):
    """대한민국 법원 대법원 선고예정 판결 크롤러."""

    LIST_PATH = "/supreme/info/JpBoardListAction.work"
    PDF_DOWNLOAD_URL = "https://file.scourt.go.kr/AttachDownload"
    DOWNLOAD_PATTERN = re.compile(r"download\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)")
    TAX_KEYWORDS = (
        "법인세",
        "소득세",
        "부가가치세",
        "상속세",
        "증여세",
        "취득세",
        "등록면허세",
        "재산세",
        "종합부동산세",
        "양도소득세",
        "관세",
        "지방세",
        "국세",
        "조세",
        "과세처분",
        "부과처분",
        "경정청구",
        "경정거부",
    )

    allows_empty_result = True

    def __init__(self):
        super().__init__("대법원 선고예정 판결", "scourt_scheduled_decisions")
        site_def = get_site(self.site_key)
        self.url = site_def.url
        self.data_columns = list(site_def.data_columns)
        self._key_column = site_def.key_column
        self.last_checked_count = 0

    def get_key_column(self) -> str:
        return self._key_column

    def postprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty or "선고일자" not in data.columns:
            return data

        data = data.copy()
        data = data.sort_values(
            by=["선고일자", "사건번호"],
            ascending=[False, False],
            kind="stable",
        )
        return data.reset_index(drop=True)

    def crawl(self, progress_callback=None, status_callback=None, **kwargs) -> pd.DataFrame:
        """대법원 선고예정 판결 목록을 1~5페이지 범위에서 수집합니다."""
        max_pages = min(int(kwargs.get("max_pages", 5)), 5)
        self.last_checked_count = 0
        self.update_status_safely(status_callback, f"{self.site_name} 크롤링 시작...")

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        })

        collected: List[Dict[str, str]] = []
        for page in range(1, max_pages + 1):
            self.update_status_safely(
                status_callback,
                f"{self.site_name} 목록 {page}/{max_pages} 페이지 확인 중...",
            )
            soup = self._fetch_soup(session, {"gubun": "1", "pageIndex": str(page)})
            rows = self._extract_list_rows(soup)
            if not rows:
                self.logger.info(f"{self.site_name}: {page}페이지에서 목록 행 없음, 중단")
                break

            self.last_checked_count += len(rows)
            collected.extend(rows)
            self.update_progress_safely(progress_callback, int((page / max_pages) * 100))

        result = pd.DataFrame(collected, columns=self.data_columns)
        result = self.preprocess_data(result)
        result = self.postprocess_data(result)

        self.update_progress_safely(progress_callback, 100)
        self.update_status_safely(
            status_callback,
            f"{self.site_name} 크롤링 완료: {len(result)}개 수집",
        )
        return result

    def _fetch_soup(self, session: requests.Session, params: Dict[str, str]) -> BeautifulSoup:
        url = urljoin(self.url, self.LIST_PATH)
        last_error = None

        for attempt in range(self.config["retry_count"]):
            try:
                response = session.get(url, params=params, timeout=self.config["timeout"])
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as e:
                last_error = e
                if attempt < self.config["retry_count"] - 1:
                    import time
                    time.sleep(self.config["retry_delay"])

        raise last_error

    def _extract_list_rows(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        rows = []

        for tr in soup.select("table tbody tr"):
            cells = tr.select("td")
            if len(cells) < 5:
                continue

            panel = cells[0].get_text(" ", strip=True)
            decision_date = self._normalize_decision_date(cells[1].get_text(" ", strip=True))
            case_type = cells[2].get_text(" ", strip=True)
            case_number = cells[3].get_text(" ", strip=True)
            title = cells[4].get_text(" ", strip=True)
            if not decision_date or not case_number or not title:
                continue

            issue_pdf = self._extract_pdf_link(cells[5]) if len(cells) > 5 else ""
            press_link = self._extract_press_link(cells[7]) if len(cells) > 7 else ""
            matched_keywords = self._match_tax_keywords(title)

            rows.append({
                "고유키": self._build_unique_key(decision_date, case_number, title),
                "선고일자": decision_date,
                "재판부": panel,
                "사건종류": case_type,
                "사건번호": case_number,
                "사건명": title,
                "조세관련": "조세후보" if matched_keywords else SCOURT_NON_TAX_STATUS,
                "관련키워드": ", ".join(matched_keywords),
                "쟁점PDF": issue_pdf,
                "보도자료링크": press_link,
            })

        return rows

    def _extract_pdf_link(self, cell) -> str:
        link = cell.select_one("a")
        href = link.get("href", "") if link else ""
        match = self.DOWNLOAD_PATTERN.search(href)
        if not match:
            return ""

        file_id, file_name = match.group(1), match.group(2)
        return f"{self.PDF_DOWNLOAD_URL}?{urlencode({'file': file_id, 'path': '048', 'downFile': file_name})}"

    def _extract_press_link(self, cell) -> str:
        link = cell.select_one("a")
        href = link.get("href", "") if link else ""
        if not href or href.startswith("javascript:"):
            return ""
        return urljoin(self.url, href)

    def _normalize_decision_date(self, raw_date: str) -> str:
        raw_date = (raw_date or "").strip()
        match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", raw_date)
        if not match:
            return raw_date

        year, month, day = match.groups()
        full_year = 2000 + int(year)
        try:
            return datetime(full_year, int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            return raw_date

    def _match_tax_keywords(self, title: str) -> List[str]:
        return [keyword for keyword in self.TAX_KEYWORDS if keyword in title]

    def _build_unique_key(self, decision_date: str, case_number: str, title: str) -> str:
        return f"{decision_date}|{case_number}|{title}"
