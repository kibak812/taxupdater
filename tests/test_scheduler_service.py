import threading
import unittest

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


def make_scheduler_service():
    service = SchedulerService.__new__(SchedulerService)
    service.logger = FakeLogger()
    service.running_jobs = set()
    service.crawl_lock = threading.RLock()
    service._crawl_context = threading.local()
    service.crawling_service = FakeCrawlingService()
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


if __name__ == "__main__":
    unittest.main()
