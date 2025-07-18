"""
스케줄링 서비스
APScheduler를 사용한 주기적 크롤링 시스템
"""

import os
import sqlite3
import asyncio
import json
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
                # 크롤링 실행하고 상세 결과 받기
                crawl_result = self.crawling_service.execute_crawling(
                    choice, None, None, is_periodic=True
                )
                success = crawl_result.get('status') == 'success'
                
                end_time = datetime.now()
                duration = int((end_time - start_time).total_seconds())
                
                if success:
                    # 성공 처리
                    self._handle_crawl_success(site_key, session_id, duration, is_manual, crawl_result)
                else:
                    # 실패 처리
                    error_msg = crawl_result.get('error', '알 수 없는 오류')
                    self._handle_crawl_failure(site_key, session_id, duration, error_msg)
                
                return crawl_result
            else:
                self.logger.error("크롤링 서비스가 설정되지 않음")
                raise ValueError("크롤링 서비스가 설정되지 않음")
            
        except Exception as e:
            # 예외 처리
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            self._handle_crawl_failure(site_key, session_id, duration, str(e))
            
        finally:
            # 실행 중 상태 제거
            self.running_jobs.discard(site_key)
            self._update_system_status(site_key, 'healthy')
    
    def _execute_all_sites_crawl(self):
        """전체 사이트 크롤링 실행 및 로그 기록"""
        start_time = datetime.now()
        log_id = None
        site_results = {}
        total_new_count = 0
        
        try:
            # 크롤링 실행 로그 시작 기록
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO crawl_execution_log 
                    (execution_type, trigger_source, start_time, status, total_sites)
                    VALUES ('scheduled', 'scheduler', ?, 'running', 
                        (SELECT COUNT(*) FROM crawl_schedules WHERE enabled = 1))
                """, (start_time.isoformat(),))
                log_id = cursor.lastrowid
                conn.commit()
            
            self.logger.info(f"전체 크롤링 시작 (로그 ID: {log_id})")
            
            # 활성화된 모든 사이트 크롤링 실행
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT site_key, site_name 
                    FROM crawl_schedules 
                    WHERE enabled = 1 
                    ORDER BY priority DESC
                """)
                sites = cursor.fetchall()
            
            success_count = 0
            failed_count = 0
            
            for site_key, site_name in sites:
                try:
                    # 개별 사이트 크롤링 실행
                    self.logger.info(f"크롤링 중: {site_name} ({site_key})")
                    
                    # 크롤링 실행하고 상세 결과 받기
                    crawl_result = self._execute_crawl_job(site_key, is_manual=False)
                    
                    if crawl_result and crawl_result.get('results'):
                        # 개별 사이트 결과에서 해당 사이트 정보 추출
                        site_result = None
                        for result in crawl_result['results']:
                            if result.get('site_key') == site_key:
                                site_result = result
                                break
                        
                        if site_result and site_result.get('status') == 'success':
                            site_results[site_key] = {
                                "status": "success",
                                "new_count": site_result.get('new_count', 0),
                                "total_crawled": site_result.get('total_crawled', 0),
                                "existing_count": site_result.get('existing_count', 0),
                                "site_name": site_name
                            }
                            total_new_count += site_result.get('new_count', 0)
                            success_count += 1
                        else:
                            # 결과는 있지만 실패한 경우
                            site_results[site_key] = {
                                "status": "failed",
                                "error": site_result.get('error_message', '알 수 없는 오류') if site_result else '크롤링 결과 없음',
                                "site_name": site_name
                            }
                            failed_count += 1
                    else:
                        # 크롤링 결과가 없는 경우
                        site_results[site_key] = {
                            "status": "failed", 
                            "error": "크롤링 결과 없음",
                            "site_name": site_name
                        }
                        failed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"{site_name} 크롤링 실패: {e}")
                    site_results[site_key] = {
                        "status": "failed",
                        "error": str(e),
                        "site_name": site_name
                    }
                    failed_count += 1
            
            # 최종 상태 결정
            if failed_count == 0:
                final_status = "success"
            elif success_count > 0:
                final_status = "partial_success"
            else:
                final_status = "failed"
            
            # 크롤링 실행 로그 완료 기록
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE crawl_execution_log
                    SET end_time = ?, status = ?, success_sites = ?, failed_sites = ?,
                        site_results = ?, total_new_data_count = ?, 
                        total_duration_seconds = ?
                    WHERE log_id = ?
                """, (
                    end_time.isoformat(), final_status, success_count, failed_count,
                    json.dumps(site_results, ensure_ascii=False), total_new_count, 
                    duration, log_id
                ))
                conn.commit()
            
            self.logger.info(f"전체 크롤링 완료: 성공 {success_count}, 실패 {failed_count}, "
                           f"신규 데이터 {total_new_count}개 (소요시간: {duration}초)")
            
            # 신규 데이터가 있으면 알림 발송
            if total_new_count > 0:
                try:
                    summary = self._create_crawl_summary(site_results)
                    asyncio.run(self.notification_service.send_all_sites_notification(
                        total_new_count, summary, f"crawl_log_{log_id}"
                    ))
                except Exception as e:
                    self.logger.warning(f"전체 크롤링 알림 발송 실패: {e}")
                    
        except Exception as e:
            self.logger.error(f"전체 크롤링 실행 실패: {e}")
            
            # 에러 로그 기록
            if log_id:
                end_time = datetime.now()
                duration = int((end_time - start_time).total_seconds())
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE crawl_execution_log
                        SET end_time = ?, status = 'failed', 
                            error_summary = ?, total_duration_seconds = ?
                        WHERE log_id = ?
                    """, (end_time.isoformat(), str(e), duration, log_id))
                    conn.commit()
    
    def _get_site_data_count(self, site_key: str) -> int:
        """사이트의 현재 데이터 개수 조회"""
        try:
            table_name = self._get_table_name(site_key)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"데이터 개수 조회 실패 ({site_key}): {e}")
            return 0
    
    def _get_recent_site_data_count(self, site_key: str, minutes: int = 10) -> int:
        """사이트의 최근 생성된 데이터 개수 조회 (크롤링 시간 기준)"""
        try:
            table_name = self._get_table_name(site_key)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 테이블 존재 확인
                cursor.execute(f"""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='{table_name}'
                """)
                
                if not cursor.fetchone():
                    return 0
                
                # 컬럼 존재 확인
                cursor.execute(f"PRAGMA table_info([{table_name}])")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # 시간 컬럼이 있는 경우만 최근 데이터 조회
                if 'created_at' in existing_columns or 'updated_at' in existing_columns:
                    time_column = 'created_at' if 'created_at' in existing_columns else 'updated_at'
                    
                    # 최근 N분 내 데이터 개수 조회 (로컬 시간 기준)
                    query = f"""
                        SELECT COUNT(*) FROM [{table_name}]
                        WHERE {time_column} >= datetime('now', 'localtime', '-{minutes} minutes')
                    """
                    
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    return count
                else:
                    # 시간 컬럼이 없으면 0 반환 (신규 데이터 없음으로 간주)
                    return 0
                    
        except Exception as e:
            self.logger.error(f"최근 데이터 개수 조회 실패 ({site_key}): {e}")
            return 0
    
    def _get_table_name(self, site_key: str) -> str:
        """site_key에서 테이블 이름 반환"""
        return f"{site_key}_data"
    
    def _create_crawl_summary(self, site_results: dict) -> str:
        """크롤링 결과 요약 생성"""
        summary_parts = []
        for site_key, result in site_results.items():
            if result["status"] == "success" and result["new_count"] > 0:
                summary_parts.append(f"{result['site_name']} {result['new_count']}건")
        
        if summary_parts:
            return "신규 발견: " + ", ".join(summary_parts)
        else:
            return "신규 데이터 없음"
    
    def _handle_crawl_success(self, site_key: str, session_id: str, 
                             duration: int, is_manual: bool, crawl_result: dict = None):
        """크롤링 성공 처리"""
        try:
            # 새로운 데이터 확인
            new_data_count = self._check_new_data_count(site_key, session_id)
            
            # 크롤링 실행 로그 저장
            self._save_crawl_execution_log(site_key, session_id, duration, 'success', 
                                         is_manual, crawl_result, new_data_count)
            
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
                try:
                    # ThreadPoolExecutor에서는 새 이벤트 루프 필요
                    asyncio.run(self.notification_service.send_new_data_notification(
                        site_key, new_data_count, session_id
                    ))
                except Exception as async_error:
                    self.logger.warning(f"새로운 데이터 알림 발송 실패: {async_error}")
            
            self.logger.info(f"크롤링 성공: {site_key} (소요시간: {duration}초, 신규: {new_data_count}개)")
            
        except Exception as e:
            self.logger.error(f"크롤링 성공 처리 실패: {e}")
    
    def _handle_crawl_failure(self, site_key: str, session_id: str, 
                            duration: int, error_message: str):
        """크롤링 실패 처리"""
        try:
            # 크롤링 실행 로그 저장
            self._save_crawl_execution_log(site_key, session_id, duration, 'failed', 
                                         False, None, 0, error_message)
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
            
            # 에러 알림 발송 (ThreadPoolExecutor에서 새 이벤트 루프 사용)
            try:
                asyncio.run(self.notification_service.send_error_notification(
                    site_key, error_message, session_id
                ))
            except Exception as async_error:
                self.logger.warning(f"에러 알림 발송 실패: {async_error}")
            
            self.logger.error(f"크롤링 실패: {site_key} (에러: {error_message})")
            
        except Exception as e:
            self.logger.error(f"크롤링 실패 처리 실패: {e}")
    
    def _check_new_data_count(self, site_key: str, session_id: str) -> int:
        """새로운 데이터 개수 확인 (실제 생성된 데이터 기준)"""
        try:
            # 최근 5분 내에 실제로 생성된 데이터 개수 확인
            return self._get_recent_site_data_count(site_key, minutes=5)
                
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
            
            # 전체 크롤링 스케줄 (매일 오전 2시와 오후 2시)
            self.scheduler.add_job(
                func=self._execute_all_sites_crawl,
                trigger=CronTrigger(hour='2,14', minute=0, timezone=self.timezone),
                id="crawl_all_sites",
                name="전체 사이트 크롤링",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=3600
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
        """작업 이력 조회 - crawl_execution_log에서 실제 실행 이력 가져오기"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # crawl_execution_log에서 실제 실행 이력 조회
                if site_key:
                    # 특정 사이트의 이력을 site_results JSON에서 필터링
                    cursor.execute("""
                        SELECT log_id, execution_type, trigger_source, start_time, end_time, 
                               status, site_results, total_new_data_count, total_duration_seconds, 
                               error_summary, created_at
                        FROM crawl_execution_log 
                        WHERE site_results LIKE ?
                        ORDER BY start_time DESC
                        LIMIT ?
                    """, (f'%"{site_key}"%', limit))
                else:
                    # 전체 실행 이력 조회
                    cursor.execute("""
                        SELECT log_id, execution_type, trigger_source, start_time, end_time, 
                               status, site_results, total_new_data_count, total_duration_seconds, 
                               error_summary, created_at
                        FROM crawl_execution_log 
                        ORDER BY start_time DESC
                        LIMIT ?
                    """, (limit,))
                
                history = []
                
                for row in cursor.fetchall():
                    log_id, execution_type, trigger_source, start_time, end_time, status, site_results_json, total_new_data, duration, error_summary, created_at = row
                    
                    # site_results JSON 파싱
                    site_results = {}
                    if site_results_json:
                        try:
                            site_results = json.loads(site_results_json)
                        except json.JSONDecodeError:
                            self.logger.warning(f"Invalid JSON in site_results for log_id {log_id}")
                    
                    if site_key:
                        # 특정 사이트 필터링 - 해당 사이트의 결과만 반환
                        if site_key in site_results:
                            site_result = site_results[site_key]
                            history.append({
                                'job_id': log_id,
                                'site_key': site_key,
                                'site_name': site_result.get('site_name', site_key),
                                'start_time': start_time,
                                'end_time': end_time,
                                'status': site_result.get('status', 'unknown'),
                                'new_count': site_result.get('new_count', 0),
                                'total_crawled': site_result.get('total_crawled', 0),
                                'existing_count': site_result.get('existing_count', 0),
                                'data_collected': site_result.get('new_count', 0),  # 하위 호환성
                                'execution_type': execution_type,
                                'trigger_source': trigger_source,
                                'error_message': error_summary if status == 'failed' else None
                            })
                    else:
                        # 전체 실행 로그 - 각 사이트별로 개별 항목 생성
                        if site_results:
                            for sk, result in site_results.items():
                                history.append({
                                    'job_id': f"{log_id}_{sk}",
                                    'site_key': sk,
                                    'site_name': result.get('site_name', sk),
                                    'start_time': start_time,
                                    'end_time': end_time,
                                    'status': result.get('status', 'unknown'),
                                    'new_count': result.get('new_count', 0),
                                    'total_crawled': result.get('total_crawled', 0),
                                    'existing_count': result.get('existing_count', 0),
                                    'data_collected': result.get('new_count', 0),  # 하위 호환성
                                    'execution_type': execution_type,
                                    'trigger_source': trigger_source,
                                    'error_message': error_summary if result.get('status') == 'failed' else None
                                })
                        else:
                            # site_results가 비어있는 경우 전체 로그 정보만 표시
                            history.append({
                                'job_id': log_id,
                                'site_key': 'all',
                                'site_name': '전체',
                                'start_time': start_time,
                                'end_time': end_time,
                                'status': status,
                                'data_collected': total_new_data or 0,
                                'execution_type': execution_type,
                                'trigger_source': trigger_source,
                                'error_message': error_summary if status == 'failed' else None
                            })
                
                return history
                
        except Exception as e:
            self.logger.error(f"작업 이력 조회 실패: {e}")
            return []
    
    def _save_crawl_execution_log(self, site_key: str, session_id: str, duration: int, 
                                 status: str, is_manual: bool, crawl_result: dict = None, 
                                 new_count: int = 0, error_message: str = None):
        """개별 크롤링 실행 로그 저장"""
        try:
            start_time = datetime.now() - timedelta(seconds=duration)
            end_time = datetime.now()
            
            # 사이트 이름 매핑
            site_names = {
                "tax_tribunal": "조세심판원",
                "nts_authority": "국세청(유권해석)",
                "nts_precedent": "국세청(판례)",
                "moef": "기획재정부",
                "mois": "행정안전부", 
                "bai": "감사원"
            }
            
            # crawl_result에서 상세 정보 추출
            total_crawled = 0
            existing_count = 0
            if crawl_result and 'results' in crawl_result:
                for result in crawl_result['results']:
                    if result.get('site_key') == site_key:
                        total_crawled = result.get('total_crawled', 0)
                        existing_count = result.get('existing_count', 0)
                        break
            
            # site_results JSON 구성
            site_results = {
                site_key: {
                    'status': status,
                    'total_crawled': total_crawled,
                    'new_count': new_count,
                    'existing_count': existing_count,
                    'site_name': site_names.get(site_key, site_key)
                }
            }
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO crawl_execution_log 
                    (execution_type, trigger_source, start_time, end_time, 
                     status, total_sites, total_new_data_count, site_results, error_summary)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    'manual' if is_manual else 'scheduled',
                    'manual' if is_manual else 'scheduler',
                    start_time.isoformat(),
                    end_time.isoformat(),
                    status,
                    new_count,
                    json.dumps(site_results),
                    error_message
                ))
                
                log_id = cursor.lastrowid
                self.logger.info(f"크롤링 실행 로그 저장됨: {site_key} (ID: {log_id})")
                
        except Exception as e:
            self.logger.error(f"크롤링 실행 로그 저장 실패: {e}")

    def clear_job_history(self) -> bool:
        """크롤링 진행현황 모두 삭제"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # crawl_execution_log 테이블의 모든 레코드 삭제
                cursor.execute("DELETE FROM crawl_execution_log")
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"크롤링 진행현황 삭제 완료: {deleted_count}개 항목 삭제")
                return True
                
        except Exception as e:
            self.logger.error(f"크롤링 진행현황 삭제 실패: {e}")
            return False
    
    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'scheduler') and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
        except:
            pass