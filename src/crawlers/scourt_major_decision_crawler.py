"""
전국법원 주요판결 크롤러

목록 페이지가 서버 렌더링 HTML을 제공하므로 Selenium 없이 requests와
BeautifulSoup만 사용합니다. 사이트의 "번호"가 등록순으로 증가한다는 점을
활용해 기존 최대 번호를 만나면 즉시 중단합니다.
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config.sites import get_site
from src.crawlers.base_crawler import BaseCrawler


class ScourtMajorDecisionCrawler(BaseCrawler):
    """대한민국 법원 전국법원 주요판결 크롤러."""

    LIST_PATH = "/portal/dcboard/DcNewsListAction.work"
    DETAIL_PATH = "/portal/dcboard/DcNewsViewAction.work"
    VIEW_PATTERN = re.compile(r"fn_view\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)")

    supports_numeric_stop = True
    allows_empty_result = True

    def __init__(self):
        super().__init__("전국법원 주요판결", "scourt_major_decisions")
        site_def = get_site(self.site_key)
        self.url = site_def.url
        self.data_columns = list(site_def.data_columns)
        self._key_column = site_def.key_column
        self.last_checked_count = 0

    def get_key_column(self) -> str:
        return self._key_column

    def postprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty or "번호" not in data.columns:
            return data

        data = data.copy()
        data["_number_sort"] = pd.to_numeric(data["번호"], errors="coerce")
        data = data.sort_values(by="_number_sort", ascending=False)
        data = data.drop(columns=["_number_sort"])
        return data.reset_index(drop=True)

    def crawl(self, progress_callback=None, status_callback=None, **kwargs) -> pd.DataFrame:
        """전국법원 주요판결 목록을 번호 기반으로 증분 수집합니다."""
        max_pages = kwargs.get("max_pages", self.config["max_pages"])
        stop_at_key = self._to_int(kwargs.get("stop_at_key"))
        detail_delay = kwargs.get("detail_delay", 0.1)

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
        should_stop = False

        for page in range(1, max_pages + 1):
            self.update_status_safely(
                status_callback,
                f"{self.site_name} 목록 {page}/{max_pages} 페이지 확인 중...",
            )

            soup = self._fetch_soup(session, self.LIST_PATH, {"gubun": "44", "pageIndex": str(page)})
            rows = self._extract_list_rows(soup)
            if not rows:
                self.logger.info(f"{self.site_name}: {page}페이지에서 목록 행 없음, 중단")
                break

            first_number = self._to_int(rows[0].get("번호"))
            if stop_at_key is not None and first_number is not None and first_number <= stop_at_key:
                self.logger.info(
                    f"{self.site_name}: 첫 행 번호 {first_number} <= 기존 최대 {stop_at_key}, 중단"
                )
                break

            for row in rows:
                self.last_checked_count += 1
                number = self._to_int(row.get("번호"))

                if stop_at_key is not None and number is not None and number <= stop_at_key:
                    self.logger.info(
                        f"{self.site_name}: 기존 번호 {number} 도달 (최대 {stop_at_key}), 중단"
                    )
                    should_stop = True
                    break

                detail = self._fetch_detail(session, row)
                if detail:
                    row.update({key: value for key, value in detail.items() if value})

                collected.append({column: row.get(column, "") for column in self.data_columns})

                if detail_delay:
                    time.sleep(detail_delay)

            self.update_progress_safely(progress_callback, int((page / max_pages) * 100))

            if should_stop:
                break

        result = pd.DataFrame(collected, columns=self.data_columns)
        result = self.preprocess_data(result)
        result = self.postprocess_data(result)

        self.update_progress_safely(progress_callback, 100)
        self.update_status_safely(
            status_callback,
            f"{self.site_name} 크롤링 완료: 신규 후보 {len(result)}개 수집",
        )
        return result

    def _fetch_soup(self, session: requests.Session, path: str, params: Dict[str, str]) -> BeautifulSoup:
        url = urljoin(self.url, path)
        last_error = None

        for attempt in range(self.config["retry_count"]):
            try:
                response = session.get(url, params=params, timeout=self.config["timeout"])
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as e:
                last_error = e
                if attempt < self.config["retry_count"] - 1:
                    time.sleep(self.config["retry_delay"])

        raise last_error

    def _extract_list_rows(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        rows = []

        for tr in soup.select("table tbody tr"):
            cells = tr.select("td")
            if len(cells) < 3:
                continue

            number = cells[0].get_text(strip=True)
            if not number.isdigit():
                continue

            link = cells[1].select_one("a")
            title = link.get_text(" ", strip=True) if link else cells[1].get_text(" ", strip=True)
            court = cells[2].get_text(" ", strip=True)
            onclick = link.get("onclick", "") if link else ""
            seqnum, cbub_code = self._parse_view_args(onclick)
            detail_link = self._build_detail_url(seqnum, cbub_code) if seqnum and cbub_code else ""

            rows.append({
                "번호": number,
                "작성일": "",
                "법원": court,
                "제목": title,
                "링크": detail_link,
                "seqnum": seqnum,
                "cbub_code": cbub_code,
            })

        return rows

    def _fetch_detail(self, session: requests.Session, row: Dict[str, str]) -> Dict[str, str]:
        seqnum = row.get("seqnum")
        cbub_code = row.get("cbub_code")
        if not seqnum or not cbub_code:
            return {}

        try:
            soup = self._fetch_soup(
                session,
                self.DETAIL_PATH,
                {"cbub_code": cbub_code, "gubun": "44", "seqnum": seqnum},
            )
            return self._extract_detail_fields(soup)
        except Exception as e:
            self.logger.warning(f"{self.site_name}: 상세 페이지 조회 실패 ({row.get('번호')}): {e}")
            return {}

    def _extract_detail_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        fields: Dict[str, str] = {}

        for tr in soup.select("table tr"):
            headers = [cell.get_text(" ", strip=True) for cell in tr.select("th")]
            values = [cell.get_text(" ", strip=True) for cell in tr.select("td")]

            if not headers or not values:
                continue

            if headers[0] == "제목":
                fields["제목"] = values[0]

            for idx, header in enumerate(headers):
                if header == "작성일" and idx < len(values):
                    fields["작성일"] = values[idx]
                    break

        return fields

    def _parse_view_args(self, onclick: str) -> tuple[str, str]:
        match = self.VIEW_PATTERN.search(onclick or "")
        if not match:
            return "", ""
        return match.group(1), match.group(2)

    def _build_detail_url(self, seqnum: str, cbub_code: str) -> str:
        return (
            f"{urljoin(self.url, self.DETAIL_PATH)}"
            f"?cbub_code={cbub_code}&gubun=44&seqnum={seqnum}"
        )

    def _to_int(self, value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None
