import os
import threading
import unittest
import sqlite3
import tempfile
import pytz

from src.services.scheduler_service import SchedulerService


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def info(self, *args, **kwargs):
        pass

    def warning(self, message, *args, **kwargs):
        self.warnings.append(str(message))

    def error(self, *args, **kwargs):
        pass


class FakeCrawlingService:
    def __init__(self):
        self.calls = []

    def execute_crawling(self, choice, progress, status, is_periodic):
        self.calls.append(
            {
                "choice": choice,
                "progress": progress,
                "status": status,
                "is_periodic": is_periodic,
            }
        )
        return {
            "status": "success",
            "results": [
                {
                    "site_key": "tax_tribunal",
                    "status": "success",
                    "new_count": 0,
                    "total_crawled": 1,
                    "existing_count": 0,
                }
            ],
        }


class FailingCrawlingService:
    def execute_crawling(self, choice, progress, status, is_periodic):
        return {
            "status": "error",
            "error": "tax_tribunal: 크롤링 결과 없음",
            "results": [
                {
                    "site_key": "tax_tribunal",
                    "status": "error",
                    "error_message": "크롤링 결과 없음",
                }
            ],
        }


class FakeJob:
    def __init__(self, job_id, **kwargs):
        self.id = job_id
        self.kwargs = kwargs
        self.next_run_time = None


class FakeScheduler:
    def __init__(self):
        self.jobs = {}

    def add_job(self, **kwargs):
        job = FakeJob(kwargs["id"], **kwargs)
        self.jobs[job.id] = job
        return job

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def get_jobs(self):
        return list(self.jobs.values())

    def remove_job(self, job_id):
        del self.jobs[job_id]


def make_scheduler_service():
    service = SchedulerService.__new__(SchedulerService)
    service.logger = FakeLogger()
    service.running_jobs = set()
    service.crawl_lock = threading.RLock()
    service._crawl_context = threading.local()
    service.crawling_service = FakeCrawlingService()
    service.site_job_ids = {}
    service._update_system_status = lambda *args, **kwargs: None
    service._handle_crawl_success = lambda *args, **kwargs: None
    service._handle_crawl_failure = lambda *args, **kwargs: None
    return service


class SchedulerServiceLockTests(unittest.TestCase):
    def hold_lock_in_background(self, service):
        lock_ready = threading.Event()
        release_lock = threading.Event()

        def hold_lock():
            service.crawl_lock.acquire()
            lock_ready.set()
            release_lock.wait(timeout=5)
            service.crawl_lock.release()

        thread = threading.Thread(target=hold_lock)
        thread.start()
        self.assertTrue(lock_ready.wait(timeout=1))
        return release_lock, thread

    def test_site_crawl_skips_when_another_crawl_holds_global_lock(self):
        service = make_scheduler_service()
        release_lock, thread = self.hold_lock_in_background(service)

        try:
            result = service._execute_crawl_job("tax_tribunal")
        finally:
            release_lock.set()
            thread.join(timeout=1)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "crawl_already_running")
        self.assertEqual(service.crawling_service.calls, [])
        self.assertEqual(service.running_jobs, set())
        self.assertTrue(service.logger.warnings)

    def test_full_crawl_skips_when_another_crawl_holds_global_lock(self):
        service = make_scheduler_service()
        release_lock, thread = self.hold_lock_in_background(service)

        try:
            result = service._execute_all_sites_crawl()
        finally:
            release_lock.set()
            thread.join(timeout=1)

        self.assertEqual(result, {"status": "skipped", "reason": "crawl_already_running"})
        self.assertFalse(service._is_full_crawl_context())

    def test_full_crawl_context_allows_nested_site_crawl(self):
        service = make_scheduler_service()
        release_lock, thread = self.hold_lock_in_background(service)

        try:
            service._crawl_context.full_crawl = True
            result = service._execute_crawl_job("tax_tribunal")
        finally:
            service._crawl_context.full_crawl = False
            release_lock.set()
            thread.join(timeout=1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(service.crawling_service.calls), 1)
        self.assertEqual(service.running_jobs, set())

    def test_failed_site_crawl_does_not_mark_system_healthy(self):
        service = make_scheduler_service()
        service.crawling_service = FailingCrawlingService()
        status_updates = []
        failures = []
        successes = []
        service._update_system_status = lambda site_key, status, *args: status_updates.append((site_key, status))
        service._handle_crawl_failure = lambda *args: failures.append(args)
        service._handle_crawl_success = lambda *args, **kwargs: successes.append(args)

        result = service._execute_crawl_job("tax_tribunal")

        self.assertEqual(result["status"], "error")
        self.assertEqual(len(failures), 1)
        self.assertEqual(successes, [])
        self.assertEqual(status_updates, [("tax_tribunal", "running")])
        self.assertEqual(service.running_jobs, set())


class FakeNotificationService:
    def __init__(self):
        self.new_data_calls = []

    async def send_new_data_notification(self, site_key, new_data_count, session_id):
        self.new_data_calls.append((site_key, new_data_count, session_id))
        return True


class SchedulerServiceNotificationTests(unittest.TestCase):
    def make_service_for_success_handling(self, full_crawl=False):
        tmp = tempfile.NamedTemporaryFile(suffix=".db")
        tmp.close()
        with sqlite3.connect(tmp.name) as conn:
            conn.execute("""
                CREATE TABLE crawl_schedules (
                    site_key TEXT PRIMARY KEY,
                    last_run TIMESTAMP,
                    last_success TIMESTAMP,
                    success_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO crawl_schedules (site_key, success_count)
                VALUES ('tax_tribunal', 0)
            """)
        self.addCleanup(lambda: os.remove(tmp.name))

        service = make_scheduler_service()
        service._handle_crawl_success = SchedulerService._handle_crawl_success.__get__(service, SchedulerService)
        service.db_path = tmp.name
        service.notification_service = FakeNotificationService()
        service._crawl_context.full_crawl = full_crawl
        service._check_new_data_count = lambda site_key, session_id: 3
        service._save_crawl_execution_log = lambda *args, **kwargs: None
        service._update_crawl_metadata = lambda *args, **kwargs: None
        return service

    def test_full_crawl_site_success_does_not_send_site_level_new_data_notification(self):
        service = self.make_service_for_success_handling(full_crawl=True)

        service._handle_crawl_success("tax_tribunal", "session-1", 1, False, {"status": "success"})

        self.assertEqual(service.notification_service.new_data_calls, [])

    def test_standalone_site_success_still_sends_new_data_notification(self):
        service = self.make_service_for_success_handling(full_crawl=False)

        service._handle_crawl_success("tax_tribunal", "session-1", 1, False, {"status": "success"})

        self.assertEqual(
            service.notification_service.new_data_calls,
            [("tax_tribunal", 3, "session-1")],
        )


class SchedulerServiceScheduleLoadingTests(unittest.TestCase):
    def make_service_with_schedule_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db")
        tmp.close()

        with sqlite3.connect(tmp.name) as conn:
            conn.execute("""
                CREATE TABLE crawl_schedules (
                    site_key TEXT NOT NULL UNIQUE,
                    site_name TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    priority INTEGER DEFAULT 0
                )
            """)
            conn.executemany("""
                INSERT INTO crawl_schedules
                (site_key, site_name, cron_expression, enabled, priority)
                VALUES (?, ?, ?, ?, ?)
            """, [
                ("tax_tribunal", "조세심판원", "0 */1 * * *", 1, 0),
                ("nts_authority", "국세청 유권해석", "0 */1 * * *", 1, 0),
                ("bai", "감사원", "0 */1 * * *", 1, 0),
                ("moef", "기획재정부", "30 */1 * * *", 1, 0),
            ])

        service = make_scheduler_service()
        service.db_path = tmp.name
        service.timezone = pytz.timezone("Asia/Seoul")
        service.scheduler = FakeScheduler()
        return service, tmp.name

    def test_same_cron_schedules_are_grouped_into_one_serial_job(self):
        service, db_path = self.make_service_with_schedule_db()
        self.addCleanup(lambda: os.remove(db_path))

        service._load_schedules_from_db()

        self.assertEqual(set(service.scheduler.jobs), {"crawl_group_1", "crawl_moef"})
        self.assertEqual(service.site_job_ids["tax_tribunal"], "crawl_group_1")
        self.assertEqual(service.site_job_ids["nts_authority"], "crawl_group_1")
        self.assertEqual(service.site_job_ids["bai"], "crawl_group_1")
        self.assertEqual(service.site_job_ids["moef"], "crawl_moef")
        self.assertEqual(
            service.scheduler.jobs["crawl_group_1"].kwargs["func"],
            service._execute_all_sites_crawl,
        )
        self.assertEqual(
            service.scheduler.jobs["crawl_group_1"].kwargs["args"],
            [["bai", "nts_authority", "tax_tribunal"]],
        )


if __name__ == "__main__":
    unittest.main()
