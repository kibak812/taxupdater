import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.repositories.sqlite_repository import SQLiteRepository


class SQLiteRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="taxupdater_repo_", dir="/private/tmp"))
        self.repo = SQLiteRepository(db_path=str(self.temp_dir / "tax_data.db"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_load_and_compare_new_entries(self):
        initial = pd.DataFrame(
            [
                {"세목": "부가", "생산일자": "2026-05-01", "문서번호": "A-1", "제목": "기존", "링크": ""},
                {"세목": "소득", "생산일자": "2026-05-02", "문서번호": "A-2", "제목": "기존2", "링크": ""},
            ]
        )

        self.assertTrue(self.repo.save_data("nts_authority", initial, is_incremental=True))

        loaded = self.repo.load_existing_data("nts_authority")
        self.assertEqual(len(loaded), 2)
        self.assertNotIn("created_at", loaded.columns)

        candidate = pd.DataFrame(
            [
                {"세목": "부가", "생산일자": "2026-05-01", "문서번호": "A-1", "제목": "기존", "링크": ""},
                {"세목": "법인", "생산일자": "2026-05-03", "문서번호": "A-3", "제목": "신규", "링크": ""},
            ]
        )
        new_entries = self.repo.compare_and_get_new_entries("nts_authority", candidate, "문서번호")

        self.assertEqual(new_entries["문서번호"].tolist(), ["A-3"])

    def test_incremental_save_updates_existing_auxiliary_columns(self):
        initial = pd.DataFrame(
            [
                {
                    "세목": "법인",
                    "생산일자": "2026-05-01",
                    "문서번호": "P-1",
                    "제목": "판례",
                    "결론": "",
                    "링크": "",
                }
            ]
        )
        updated = initial.copy()
        updated.loc[0, "결론"] = "인용"

        self.assertTrue(self.repo.save_data("nts_precedent", initial, is_incremental=True))
        self.assertTrue(self.repo.save_data("nts_precedent", updated, is_incremental=True))

        loaded = self.repo.load_existing_data("nts_precedent")

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded.iloc[0]["결론"], "인용")

    def test_recent_counts_uses_repository_timestamp_columns(self):
        data = pd.DataFrame(
            [
                {"번호": "10", "작성일": "2026-05-04", "법원": "서울고법", "제목": "판결", "링크": ""}
            ]
        )

        self.assertTrue(self.repo.save_data("scourt_major_decisions", data, is_incremental=True))

        counts = self.repo.get_recent_data_counts(hours=24)

        self.assertEqual(counts["scourt_major_decisions"], 1)


if __name__ == "__main__":
    unittest.main()
