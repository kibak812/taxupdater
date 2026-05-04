import unittest

import pandas as pd

from src.services.crawler_service import CrawlingService


class FakeRepository:
    db_path = ":memory:"


class FakeCrawler:
    supports_numeric_stop = True

    def get_site_name(self):
        return "가짜 크롤러"


class CrawlingServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = CrawlingService({}, FakeRepository())

    def test_get_max_numeric_key_ignores_non_numeric_values(self):
        data = pd.DataFrame({"번호": ["10", "not-a-number", "12", None, "9"]})

        self.assertEqual(self.service._get_max_numeric_key(data, "번호"), 12)
        self.assertIsNone(self.service._get_max_numeric_key(data, "없는컬럼"))

    def test_build_crawl_kwargs_uses_numeric_stop_for_supported_crawler(self):
        existing_data = pd.DataFrame({"번호": ["5", "8", "7"]})

        kwargs = self.service._build_crawl_kwargs(FakeCrawler(), existing_data, "번호")

        self.assertEqual(kwargs, {"stop_at_key": 8})

    def test_site_key_columns_are_loaded_from_catalog(self):
        self.assertEqual(self.service._get_key_column_for_site("tax_tribunal"), "청구번호")
        self.assertEqual(self.service._get_key_column_for_site("scourt_scheduled_decisions"), "고유키")
        self.assertEqual(self.service._get_key_column_for_site("unknown"), "문서번호")

    def test_new_data_samples_use_catalog_key_columns(self):
        scheduled = pd.DataFrame(
            [
                {"고유키": "2026-05-04|2026두1|사건", "사건명": "법인세 사건"},
                {"고유키": "2026-05-05|2026두2|사건", "사건명": ""},
            ]
        )

        samples = self.service._get_new_data_samples(
            scheduled,
            "scourt_scheduled_decisions",
            limit=2,
        )

        self.assertEqual(samples[0], "2026-05-04|2026두1|사건 (법인세 사건...)")
        self.assertEqual(samples[1], "2026-05-05|2026두2|사건")

    def test_scheduled_decision_summary_and_tags(self):
        row = pd.Series(
            {
                "선고일자": "2026-05-04",
                "조세관련": "조세후보",
                "관련키워드": "법인세, 경정청구",
                "사건명": "법인세 경정청구 사건",
            }
        )

        summary = self.service._create_data_summary(row, "scourt_scheduled_decisions")
        tags = self.service._generate_tags(row, "scourt_scheduled_decisions")

        self.assertEqual(summary, "2026-05-04 선고예정 (조세후보) - 법인세, 경정청구")
        self.assertIn("조세후보", tags)
        self.assertIn("키워드:법인세", tags)
        self.assertIn("키워드:경정청구", tags)


if __name__ == "__main__":
    unittest.main()
