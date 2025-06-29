"""
스케줄링 서비스
APScheduler를 사용한 주기적 크롤링 시스템
"""

import os
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import pytz

from src.config.logging_config import get_logger
from src.services.crawler_service import CrawlingService
from src.services.notification_service import NotificationService


class SchedulerService:
    """스케줄링 서비스 클래스"""
    
    def __init__(self, db_path: str = "data/tax_data.db", crawling_service=None):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        self.timezone = pytz.timezone('Asia/Seoul')
        
        # 스케줄러 초기화
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # 서비스 인스턴스 (전달받거나 나중에 설정)
        self.crawling_service = crawling_service
        self.notification_service = NotificationService(db_path)
        
        # 실행 중인 작업 추적
        self.running_jobs = set()
        self.job_results = {}
        
        # ThreadPoolExecutor for async operations
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        self.logger.info("스케줄러 서비스 초기화 완료")
    
    def start(self):
        """스케줄러 시작"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("스케줄러 시작됨")
                
                # 기존 스케줄 로드
                self._load_schedules_from_db()
                
                # 시스템 상태 업데이트 작업 추가
                self._add_system_maintenance_jobs()
                
            else:
                self.logger.warning("스케줄러가 이미 실행 중입니다")
                
        except Exception as e:
            self.logger.error(f"스케줄러 시작 실패: {e}")
            raise
    
    def stop(self):
        """스케줄러 중지"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                self.logger.info("스케줄러 중지됨")
            
            self.executor.shutdown(wait=True)
            
        except Exception as e:
            self.logger.error(f"스케줄러 중지 실패: {e}")
    
    def is_running(self) -> bool:
        """스케줄러 실행 상태 확인"""
        return self.scheduler.running
    
    def add_crawl_schedule(self, site_key: str, cron_expression: str, 
                          enabled: bool = True, priority: int = 0,
                          notification_threshold: int = 1) -> bool:
        """크롤링 스케줄 추가"""
        try:
            # 데이터베이스에 스케줄 저장
            self._save_schedule_to_db(site_key, cron_expression, enabled, 
                                    priority, notification_threshold)
            
            if enabled:
                # APScheduler에 작업 추가
                job_id = f"crawl_{site_key}"
                
                # 기존 작업 제거
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                
                # 새 작업 추가
                trigger = CronTrigger.from_crontab(cron_expression, timezone=self.timezone)
                
                self.scheduler.add_job(
                    func=self._execute_crawl_job,
                    trigger=trigger,
                    id=job_id,
                    args=[site_key],
                    name=f"크롤링: {site_key}",
                    replace_existing=True,
                    max_instances=1,  # 동시 실행 방지
                    misfire_grace_time=3600  # 1시간 지연 허용
                )
                
                self.logger.info(f"크롤링 스케줄 추가: {site_key} ({cron_expression})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"스케줄 추가 실패 ({site_key}): {e}")
            return False
    
    def remove_crawl_schedule(self, site_key: str) -> bool:
        """크롤링 스케줄 제거"""
        try:
            job_id = f"crawl_{site_key}"
            
            # APScheduler에서 제거
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # 데이터베이스에서 비활성화
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE crawl_schedules 
                    SET enabled = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE site_key = ?
                """, (site_key,))
            
            self.logger.info(f"크롤링 스케줄 제거: {site_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"스케줄 제거 실패 ({site_key}): {e}")
            return False
    
    def get_schedule_status(self, site_key: str = None) -> Dict[str, Any]:
        """스케줄 상태 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if site_key:
                    # 특정 사이트 스케줄 조회
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM crawl_schedules WHERE site_key = ?
                    """, (site_key,))
                    
                    row = cursor.fetchone()
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        schedule_data = dict(zip(columns, row))
                        
                        # APScheduler 작업 상태 추가
                        job_id = f"crawl_{site_key}"
                        job = self.scheduler.get_job(job_id)
                        schedule_data['scheduler_status'] = {
                            'active': job is not None,
                            'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
                            'running': site_key in self.running_jobs
                        }
                        
                        return schedule_data
                    else:
                        return {"error": f"스케줄 없음: {site_key}"}
                else:
                    # 전체 스케줄 조회
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM crawl_schedules ORDER BY priority DESC, site_key")
                    
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    schedules = []
                    for row in rows:
                        schedule_data = dict(zip(columns, row))
                        
                        # APScheduler 작업 상태 추가
                        job_id = f"crawl_{schedule_data['site_key']}"
                        job = self.scheduler.get_job(job_id)
                        schedule_data['scheduler_status'] = {
                            'active': job is not None,
                            'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
                            'running': schedule_data['site_key'] in self.running_jobs
                        }
                        
                        schedules.append(schedule_data)
                    
                    return {
                        'schedules': schedules,
                        'scheduler_running': self.scheduler.running,
                        'total_jobs': len(self.scheduler.get_jobs())
                    }
                    
        except Exception as e:
            self.logger.error(f"스케줄 상태 조회 실패: {e}")
            return {"error": str(e)}
    
    def trigger_manual_crawl(self, site_key: str, delay_seconds: int = 0) -> bool:
        """수동 크롤링 트리거"""
        try:
            job_id = f"manual_{site_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if delay_seconds > 0:
                # 지연 실행
                run_time = datetime.now(self.timezone) + timedelta(seconds=delay_seconds)
                trigger = DateTrigger(run_date=run_time, timezone=self.timezone)
            else:
                # 즉시 실행
                trigger = DateTrigger(run_date=datetime.now(self.timezone), timezone=self.timezone)
            
            self.scheduler.add_job(
                func=self._execute_crawl_job,
                trigger=trigger,
                id=job_id,
                args=[site_key, True],  # is_manual=True
                name=f"수동 크롤링: {site_key}",
                max_instances=1
            )
            
            self.logger.info(f"수동 크롤링 예약: {site_key} (지연: {delay_seconds}초)")
            return True
            
        except Exception as e:
            self.logger.error(f"수동 크롤링 트리거 실패 ({site_key}): {e}")
            return False
    
    def _execute_crawl_job(self, site_key: str, is_manual: bool = False):
        """크롤링 작업 실행"""
        start_time = datetime.now()
        session_id = f"{site_key}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # 중복 실행 방지
            if site_key in self.running_jobs:
                self.logger.warning(f"크롤링 이미 실행 중: {site_key}")
                return
            
            self.running_jobs.add(site_key)
            self.logger.info(f"크롤링 작업 시작: {site_key} (세션: {session_id})")
            
            # 시스템 상태 업데이트
            self._update_system_status(site_key, 'running')
            
            # 크롤링 실행
            site_to_choice = {
                "tax_tribunal": "1",
                "nts_authority": "2", 
                "moef": "3",
                "nts_precedent": "4",
                "mois": "5",
                "bai": "6"
            }
            
            choice = site_to_choice.get(site_key)
            if not choice:
                raise ValueError(f"알 수 없는 사이트: {site_key}")
            
            # 크롤링 서비스 실행
            if self.crawling_service:
                success = self.crawling_service.execute_crawling(
                    choice, None, None, is_periodic=True
                )
            else:
                self.logger.error("크롤링 서비스가 설정되지 않음")
                raise ValueError("크롤링 서비스가 설정되지 않음")
            
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            
            if success:
                # 성공 처리
                self._handle_crawl_success(site_key, session_id, duration, is_manual)
            else:
                # 실패 처리
                self._handle_crawl_failure(site_key, session_id, duration, "크롤링 실행 실패")
            
        except Exception as e:
            # 예외 처리
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            self._handle_crawl_failure(site_key, session_id, duration, str(e))
            
        finally:
            # 실행 중 상태 제거
            self.running_jobs.discard(site_key)
            self._update_system_status(site_key, 'healthy')
    
    def _handle_crawl_success(self, site_key: str, session_id: str, 
                             duration: int, is_manual: bool):
        """크롤링 성공 처리"""
        try:
            # 새로운 데이터 확인
            new_data_count = self._check_new_data_count(site_key, session_id)
            
            # 스케줄 정보 업데이트
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE crawl_schedules 
                    SET last_run = CURRENT_TIMESTAMP,
                        last_success = CURRENT_TIMESTAMP,
                        success_count = success_count + 1,
                        avg_crawl_time = (avg_crawl_time + ?) / 2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE site_key = ?
                """, (duration, site_key))
            
            # 메타데이터 업데이트
            self._update_crawl_metadata(site_key, duration, success=True)
            
            # 알림 발송 (새로운 데이터가 있을 경우)
            if new_data_count > 0:
                asyncio.create_task(self.notification_service.send_new_data_notification(
                    site_key, new_data_count, session_id
                ))
            
            self.logger.info(f"크롤링 성공: {site_key} (소요시간: {duration}초, 신규: {new_data_count}개)")
            
        except Exception as e:
            self.logger.error(f"크롤링 성공 처리 실패: {e}")
    
    def _handle_crawl_failure(self, site_key: str, session_id: str, 
                            duration: int, error_message: str):
        """크롤링 실패 처리"""
        try:
            # 스케줄 정보 업데이트
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE crawl_schedules 
                    SET last_run = CURRENT_TIMESTAMP,
                        last_failure = CURRENT_TIMESTAMP,
                        failure_count = failure_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE site_key = ?
                """, (site_key,))
            
            # 메타데이터 업데이트
            self._update_crawl_metadata(site_key, duration, success=False, error=error_message)
            
            # 시스템 상태 업데이트
            self._update_system_status(site_key, 'error', error_message)
            
            # 에러 알림 발송
            asyncio.create_task(self.notification_service.send_error_notification(
                site_key, error_message, session_id
            ))
            
            self.logger.error(f"크롤링 실패: {site_key} (에러: {error_message})")
            
        except Exception as e:
            self.logger.error(f"크롤링 실패 처리 실패: {e}")
    
    def _check_new_data_count(self, site_key: str, session_id: str) -> int:
        """새로운 데이터 개수 확인"""
        try:
            # 최근 5분 내에 추가된 데이터 개수 확인
            cutoff_time = datetime.now() - timedelta(minutes=5)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # new_data_log 테이블에서 확인
                cursor.execute("""
                    SELECT COUNT(*) FROM new_data_log 
                    WHERE site_key = ? AND discovered_at >= ?
                """, (site_key, cutoff_time.isoformat()))
                
                count = cursor.fetchone()[0]
                return count
                
        except Exception as e:
            self.logger.error(f"새로운 데이터 개수 확인 실패: {e}")
            return 0
    
    def _update_system_status(self, site_key: str, status: str, error_message: str = None):
        """시스템 상태 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if status == 'error':
                    conn.execute("""
                        UPDATE system_status 
                        SET status = ?, 
                            last_check = CURRENT_TIMESTAMP,
                            last_error = CURRENT_TIMESTAMP,
                            error_message = ?,
                            error_count = error_count + 1,
                            consecutive_errors = consecutive_errors + 1,
                            health_score = MAX(0, health_score - 10),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE site_key = ? AND component_type = 'crawler'
                    """, (status, error_message, site_key))
                else:
                    conn.execute("""
                        UPDATE system_status 
                        SET status = ?, 
                            last_check = CURRENT_TIMESTAMP,
                            last_success = CURRENT_TIMESTAMP,
                            consecutive_errors = 0,
                            health_score = MIN(100, health_score + 2),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE site_key = ? AND component_type = 'crawler'
                    """, (status, site_key))
                    
        except Exception as e:
            self.logger.error(f"시스템 상태 업데이트 실패: {e}")
    
    def _update_crawl_metadata(self, site_key: str, duration: int, 
                              success: bool, error: str = None):
        """크롤 메타데이터 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if success:
                    conn.execute("""
                        UPDATE crawl_metadata 
                        SET last_crawl = CURRENT_TIMESTAMP,
                            avg_crawl_time = (COALESCE(avg_crawl_time, 0) + ?) / 2,
                            success_rate = (success_rate * 0.9) + 10,
                            error_count = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE site_key = ?
                    """, (duration, site_key))
                else:
                    conn.execute("""
                        UPDATE crawl_metadata 
                        SET last_crawl = CURRENT_TIMESTAMP,
                            last_error = ?,
                            error_count = error_count + 1,
                            success_rate = success_rate * 0.9,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE site_key = ?
                    """, (error, site_key))
                    
        except Exception as e:
            self.logger.error(f"메타데이터 업데이트 실패: {e}")
    
    def _load_schedules_from_db(self):
        """데이터베이스에서 스케줄 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT site_key, cron_expression, enabled, priority, notification_threshold
                    FROM crawl_schedules WHERE enabled = 1
                """)
                
                for row in cursor.fetchall():
                    site_key, cron_expr, enabled, priority, threshold = row
                    
                    if enabled:
                        job_id = f"crawl_{site_key}"
                        trigger = CronTrigger.from_crontab(cron_expr, timezone=self.timezone)
                        
                        self.scheduler.add_job(
                            func=self._execute_crawl_job,
                            trigger=trigger,
                            id=job_id,
                            args=[site_key],
                            name=f"크롤링: {site_key}",
                            replace_existing=True,
                            max_instances=1,
                            misfire_grace_time=3600
                        )
                        
                        self.logger.info(f"스케줄 로드: {site_key} ({cron_expr})")
                        
        except Exception as e:
            self.logger.error(f"스케줄 로드 실패: {e}")
    
    def _add_system_maintenance_jobs(self):
        """시스템 유지보수 작업 추가"""
        try:
            # 시스템 상태 체크 (5분마다)
            self.scheduler.add_job(
                func=self._system_health_check,
                trigger=IntervalTrigger(minutes=5),
                id="system_health_check",
                name="시스템 상태 체크",
                replace_existing=True
            )
            
            # 알림 정리 (매일 자정)
            self.scheduler.add_job(
                func=self._cleanup_old_notifications,
                trigger=CronTrigger(hour=0, minute=0, timezone=self.timezone),
                id="cleanup_notifications",
                name="알림 정리",
                replace_existing=True
            )
            
            self.logger.info("시스템 유지보수 작업 추가 완료")
            
        except Exception as e:
            self.logger.error(f"유지보수 작업 추가 실패: {e}")
    
    def _system_health_check(self):
        """시스템 건강도 체크"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 각 사이트 상태 체크
                cursor.execute("SELECT DISTINCT site_key FROM crawl_schedules")
                sites = [row[0] for row in cursor.fetchall()]
                
                for site_key in sites:
                    # 마지막 성공한 크롤링 시간 확인
                    cursor.execute("""
                        SELECT last_success, consecutive_errors 
                        FROM crawl_schedules WHERE site_key = ?
                    """, (site_key,))
                    
                    result = cursor.fetchone()
                    if result:
                        last_success, consecutive_errors = result
                        
                        # 24시간 이상 성공 없음 체크
                        if last_success:
                            last_success_dt = datetime.fromisoformat(last_success)
                            if datetime.now() - last_success_dt > timedelta(hours=24):
                                self._update_system_status(site_key, 'warning', 
                                                         "24시간 이상 성공한 크롤링 없음")
                        
                        # 연속 에러 체크
                        if consecutive_errors >= 3:
                            self._update_system_status(site_key, 'error', 
                                                     f"연속 {consecutive_errors}회 실패")
                            
        except Exception as e:
            self.logger.error(f"시스템 건강도 체크 실패: {e}")
    
    def _cleanup_old_notifications(self):
        """오래된 알림 정리"""
        try:
            # 30일 이전 알림 삭제
            cutoff_date = datetime.now() - timedelta(days=30)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM notification_history 
                    WHERE created_at < ? AND status = 'read'
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                
                # 오래된 new_data_log 정리 (90일)
                cutoff_date_log = datetime.now() - timedelta(days=90)
                cursor.execute("""
                    DELETE FROM new_data_log 
                    WHERE discovered_at < ?
                """, (cutoff_date_log.isoformat(),))
                
                deleted_log_count = cursor.rowcount
                
                self.logger.info(f"알림 정리 완료: 알림 {deleted_count}개, 로그 {deleted_log_count}개 삭제")
                
        except Exception as e:
            self.logger.error(f"알림 정리 실패: {e}")
    
    def _save_schedule_to_db(self, site_key: str, cron_expression: str, 
                           enabled: bool, priority: int, notification_threshold: int):
        """스케줄을 데이터베이스에 저장"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE crawl_schedules 
                SET cron_expression = ?, enabled = ?, priority = ?, 
                    notification_threshold = ?, updated_at = CURRENT_TIMESTAMP
                WHERE site_key = ?
            """, (cron_expression, enabled, priority, notification_threshold, site_key))
    
    def _job_listener(self, event):
        """APScheduler 작업 이벤트 리스너"""
        try:
            job_id = event.job_id
            
            if event.exception:
                self.logger.error(f"작업 실패: {job_id} - {event.exception}")
            else:
                self.logger.info(f"작업 완료: {job_id}")
                
        except Exception as e:
            self.logger.error(f"작업 이벤트 처리 실패: {e}")
    
    def get_job_history(self, site_key: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """작업 이력 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if site_key:
                    cursor.execute("""
                        SELECT cs.site_key, cs.site_name, cs.last_run, cs.last_success, cs.last_failure,
                               cs.success_count, cs.failure_count, cs.avg_crawl_time
                        FROM crawl_schedules cs 
                        WHERE cs.site_key = ?
                        ORDER BY cs.last_run DESC
                        LIMIT ?
                    """, (site_key, limit))
                else:
                    cursor.execute("""
                        SELECT cs.site_key, cs.site_name, cs.last_run, cs.last_success, cs.last_failure,
                               cs.success_count, cs.failure_count, cs.avg_crawl_time
                        FROM crawl_schedules cs 
                        ORDER BY cs.last_run DESC
                        LIMIT ?
                    """, (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                history = []
                
                for row in cursor.fetchall():
                    history.append(dict(zip(columns, row)))
                
                return history
                
        except Exception as e:
            self.logger.error(f"작업 이력 조회 실패: {e}")
            return []
    
    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'scheduler') and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
        except:
            pass