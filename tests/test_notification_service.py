import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.services.notification_service import NotificationData, NotificationService


class NotificationServiceNtfyTests(unittest.TestCase):
    def make_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db")
        tmp.close()

        with sqlite3.connect(tmp.name) as conn:
            conn.execute("""
                CREATE TABLE crawl_schedules (
                    site_key TEXT PRIMARY KEY,
                    notification_threshold INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                INSERT INTO crawl_schedules (site_key, notification_threshold)
                VALUES ('tax_tribunal', 1)
            """)
            conn.execute("""
                CREATE TABLE crawl_metadata (
                    site_key TEXT PRIMARY KEY,
                    notification_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                INSERT INTO crawl_metadata (site_key, notification_count)
                VALUES ('tax_tribunal', 0)
            """)
            conn.execute("""
                CREATE TABLE notification_history (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_key TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT,
                    new_data_count INTEGER DEFAULT 0,
                    urgency_level TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'pending',
                    delivery_channels TEXT,
                    metadata TEXT,
                    read_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE new_data_log (
                    site_key TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notification_sent BOOLEAN DEFAULT 0,
                    notification_id INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE tax_tribunal_data (
                    "문서번호" TEXT,
                    "제목" TEXT,
                    "생산일자" TEXT,
                    "링크" TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.executemany("""
                INSERT INTO tax_tribunal_data ("문서번호", "제목", "생산일자", "링크", created_at)
                VALUES (?, ?, ?, ?, datetime('now', ?))
            """, [
                ("DOC-2", "최신 조세심판 사례", "2026-05-10", "https://example.com/doc-2", "localtime"),
                ("DOC-1", "이전 조세심판 사례", "2026-05-09", "https://example.com/doc-1", "localtime",),
            ])

        self.addCleanup(lambda: os.remove(tmp.name))
        return tmp.name

    @patch.dict(os.environ, {
        "NTFY_TOPIC": "tax-alerts",
        "DASHBOARD_URL": "https://dash.example",
        "NTFY_CLICK_URL": "",
    }, clear=False)
    def test_ntfy_message_summarizes_recent_new_data(self):
        service = NotificationService(self.make_db())
        notification = NotificationData(
            site_key="tax_tribunal",
            notification_type="new_data",
            title="새로운 데이터 발견: 조세심판원",
            message="조세심판원에서 2개의 새로운 데이터가 발견되었습니다.",
            new_data_count=2,
        )

        message = service._create_ntfy_message_sync(notification)

        self.assertIn("## 신규 사례 요약", message)
        self.assertIn("[최신 조세심판 사례](https://example.com/doc-2)", message)
        self.assertIn("DOC-2", message)
        self.assertIn("[대시보드 열기](https://dash.example/data/tax_tribunal)", message)

    @patch.dict(os.environ, {
        "NTFY_TOPIC": "tax-alerts",
        "DASHBOARD_URL": "https://dash.example",
        "NTFY_CLICK_URL": "https://dash.example/dashboard",
    }, clear=False)
    def test_ntfy_click_url_uses_dashboard_override(self):
        service = NotificationService(self.make_db())
        notification = NotificationData(
            site_key="tax_tribunal",
            notification_type="new_data",
            title="새로운 데이터 발견: 조세심판원",
            message="조세심판원에서 1개의 새로운 데이터가 발견되었습니다.",
            new_data_count=1,
        )

        self.assertEqual(service._ntfy_click_url(notification), "https://dash.example/dashboard")
        self.assertIn(
            "[대시보드 열기](https://dash.example/dashboard)",
            service._create_ntfy_message_sync(notification),
        )

    def test_ntfy_title_header_for_korean_text_stays_on_one_line(self):
        service = NotificationService(self.make_db())
        encoded = service._encode_ntfy_header("예규판례 모니터링 - 새로운 데이터 발견: 조세심판원")

        self.assertNotIn("\n", encoded)
        self.assertNotIn("\r", encoded)

    @patch.dict(os.environ, {
        "NTFY_TOPIC": "tax-alerts",
        "DASHBOARD_URL": "https://dash.example",
        "NTFY_CLICK_URL": "",
    }, clear=False)
    def test_new_data_notification_uses_ntfy_instead_of_email(self):
        service = NotificationService(self.make_db())
        sent = {}

        def fake_send(ntfy_url, headers, message, notification_id, max_retries=3):
            sent["url"] = ntfy_url
            sent["headers"] = headers
            sent["message"] = message
            sent["notification_id"] = notification_id
            return True

        service._sync_send_ntfy_with_retry = fake_send

        success = asyncio.run(service.send_new_data_notification("tax_tribunal", 2, "session-1"))

        self.assertTrue(success)
        self.assertEqual(sent["url"], "https://ntfy.sh/tax-alerts")
        self.assertEqual(sent["headers"]["Priority"], "default")
        self.assertIn("Markdown", sent["headers"])
        self.assertIn("최신 조세심판 사례", sent["message"])

        with sqlite3.connect(service.db_path) as conn:
            row = conn.execute("""
                SELECT delivery_channels
                FROM notification_history
                ORDER BY notification_id DESC
                LIMIT 1
            """).fetchone()

        self.assertEqual(json.loads(row[0]), ["push", "ntfy"])


if __name__ == "__main__":
    unittest.main()
