import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.web.context import ConnectionManager, WebAppContext
from src.web.factory import create_app
from src.web.helpers import build_dashboard_payload, build_site_data_payload
from src.web.routers.data import (
    _build_item_details,
    _extract_details_from_metadata,
    _first_non_empty_link,
)


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class FakeRepository:
    db_path = ":memory:"

    def get_statistics(self, site_key):
        stats = {
            "tax_tribunal": {
                "total_count": 2,
                "last_updated": "2026-05-04 10:20:30",
            },
            "empty_site": {
                "total_count": 0,
                "last_updated": None,
            },
        }
        return stats[site_key]

    def get_database_info(self):
        return {}


class FakeScheduler:
    def __init__(self):
        self.scheduler = self

    def is_running(self):
        return False

    def get_jobs(self):
        return []


EXPECTED_PUBLIC_ROUTES = [
    "/health",
    "/",
    "/dashboard",
    "/legacy",
    "/legacy/old",
    "/data/{site_key}",
    "/settings",
    "/sites/{site_key}",
    "/api/dashboard",
    "/api/sites/{site_key}/data",
    "/api/stats",
    "/api/sites/recent-counts",
    "/api/new-data",
    "/api/crawl/all",
    "/api/crawl/{site_key}",
    "/api/schedules",
    "/api/schedules/{site_key}",
    "/api/schedules",
    "/api/schedules/{site_key}",
    "/api/schedules/{site_key}/trigger",
    "/api/notifications",
    "/api/notifications/{notification_id}/read",
    "/api/notifications/stats",
    "/api/system-status",
    "/api/job-history",
    "/api/job-history",
    "/api/scheduler/start",
    "/api/scheduler/stop",
    "/api/ntfy-settings",
    "/api/email-settings",
    "/api/email-settings",
    "/api/email-settings/test",
    "/api/tunnel-status",
    "/api/tunnel/start/{tunnel_type}",
    "/api/tunnel/stop/{tunnel_type}",
    "/ws/crawl",
]


class WebRefactorTests(unittest.TestCase):
    def test_dashboard_payload_preserves_shape_and_status(self):
        site_info = {
            "tax_tribunal": {"name": "조세심판원", "color": "#3B82F6"},
            "empty_site": {"name": "빈 사이트", "color": "#000000"},
        }

        payload = build_dashboard_payload(
            site_info,
            FakeRepository(),
            now=datetime(2026, 5, 4, 12, 0, 0),
        )

        self.assertEqual(payload["last_refresh"], "2026-05-04T12:00:00")
        self.assertEqual(payload["sites"][0]["site_key"], "tax_tribunal")
        self.assertEqual(payload["sites"][0]["status"], "success")
        self.assertEqual(payload["sites"][0]["last_updated"], "2026-05-04T10:20:30")
        self.assertEqual(payload["sites"][1]["status"], "empty")

    def test_site_data_payload_searches_and_paginates(self):
        data = pd.DataFrame(
            [
                {"문서번호": "A-1", "제목": "부가가치세 판례", "created_at": "2026-05-04"},
                {"문서번호": "A-2", "제목": "소득세 해석", "created_at": "2026-05-03"},
                {"문서번호": "A-3", "제목": "부가세 신고", "created_at": "2026-05-02"},
            ]
        )
        site_info = {"nts_authority": {"name": "국세청", "color": "#10B981"}}

        payload = build_site_data_payload(
            "nts_authority",
            site_info,
            data,
            page=1,
            limit=1,
            search="부가",
            filter_type="recent",
            days=7,
        )

        self.assertEqual(payload["site_name"], "국세청")
        self.assertEqual(payload["pagination"]["total_count"], 2)
        self.assertEqual(payload["pagination"]["total_pages"], 2)
        self.assertTrue(payload["pagination"]["has_next"])
        self.assertEqual(payload["data"][0]["문서번호"], "A-1")
        self.assertEqual(payload["filter"], {"type": "recent", "days": 7, "start": None, "end": None})

    def test_app_factory_registers_routes_without_default_context(self):
        context = WebAppContext(
            project_root=Path(__file__).resolve().parents[1],
            repository=FakeRepository(),
            crawlers={"tax_tribunal": object()},
            crawling_service=object(),
            manager=ConnectionManager(),
            scheduler_service=FakeScheduler(),
            notification_service=object(),
            site_info={"tax_tribunal": {"name": "조세심판원", "color": "#3B82F6"}},
            logger=FakeLogger(),
        )

        app = create_app(context)
        paths = [route.path for route in app.routes]

        for path in EXPECTED_PUBLIC_ROUTES:
            self.assertIn(path, paths)
        self.assertLess(paths.index("/api/crawl/all"), paths.index("/api/crawl/{site_key}"))
        self.assertIs(app.state.context, context)

    def test_app_factory_preserves_route_methods(self):
        context = WebAppContext(
            project_root=Path(__file__).resolve().parents[1],
            repository=FakeRepository(),
            crawlers={"tax_tribunal": object()},
            crawling_service=object(),
            manager=ConnectionManager(),
            scheduler_service=FakeScheduler(),
            notification_service=object(),
            site_info={"tax_tribunal": {"name": "조세심판원", "color": "#3B82F6"}},
            logger=FakeLogger(),
        )

        app = create_app(context)
        route_methods = {
            route.path: route.methods
            for route in app.routes
            if hasattr(route, "methods")
        }

        self.assertEqual(route_methods["/api/dashboard"], {"GET"})
        self.assertEqual(route_methods["/api/crawl/all"], {"POST"})
        self.assertEqual(route_methods["/api/crawl/{site_key}"], {"POST"})
        self.assertEqual(route_methods["/api/job-history"], {"DELETE"})
        self.assertEqual(route_methods["/api/tunnel/start/{tunnel_type}"], {"POST"})

    def test_connection_manager_disconnect_is_idempotent(self):
        manager = ConnectionManager()
        connection = object()

        manager.active_connections.append(connection)
        manager.disconnect(connection)
        manager.disconnect(connection)

        self.assertEqual(manager.active_connections, [])

    def test_new_data_details_extract_from_original_data(self):
        metadata = {
            "original_data": {
                "세목": "양도소득세",
                "유형": "기각",
                "결론": "국승",
                "링크": "",
                "쟁점PDF": "https://example.com/issue.pdf",
            }
        }

        self.assertEqual(
            _extract_details_from_metadata(metadata),
            {
                "external_link": "https://example.com/issue.pdf",
                "data_tax_category": "양도소득세",
                "data_decision_type": "기각",
                "data_conclusion": "국승",
                "data_tax_status": "",
            },
        )

    def test_new_data_details_build_from_site_row(self):
        self.assertEqual(
            _build_item_details(
                {
                    "세목": "부가가치세",
                    "유형": "취소",
                    "결론": "국패",
                    "링크": "https://example.com/source",
                }
            ),
            {
                "external_link": "https://example.com/source",
                "data_tax_category": "부가가치세",
                "data_decision_type": "취소",
                "data_conclusion": "국패",
                "data_tax_status": "",
            },
        )

    def test_first_non_empty_link_ignores_blank_values(self):
        self.assertEqual(
            _first_non_empty_link(["", None, "#", " https://example.com/doc "]),
            "https://example.com/doc",
        )


if __name__ == "__main__":
    unittest.main()
