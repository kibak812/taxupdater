"""
데이터베이스 마이그레이션 스크립트
주기적 크롤링 및 새로운 데이터 모니터링 시스템을 위한 스키마 확장
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.config.logging_config import get_logger


class DatabaseMigration:
    """데이터베이스 마이그레이션 관리 클래스"""
    
    def __init__(self, db_path: str = "data/tax_data.db"):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        
        # 데이터베이스 폴더 생성
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def migrate_to_monitoring_system(self) -> bool:
        """모니터링 시스템용 스키마로 마이그레이션"""
        try:
            self.logger.info("모니터링 시스템 마이그레이션 시작...")
            
            # 백업 생성
            backup_path = self._create_backup()
            self.logger.info(f"데이터베이스 백업 완료: {backup_path}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 크롤링 스케줄 테이블 생성
                self._create_crawl_schedules_table(cursor)
                
                # 2. 알림 히스토리 테이블 생성
                self._create_notification_history_table(cursor)
                
                # 3. 새로운 데이터 로그 테이블 생성
                self._create_new_data_log_table(cursor)
                
                # 4. 시스템 상태 테이블 생성
                self._create_system_status_table(cursor)
                
                # 5. 크롤링 실행 로그 테이블 생성
                self._create_crawl_execution_log_table(cursor)
                
                # 6. 기존 crawl_metadata 테이블 확장
                self._extend_crawl_metadata_table(cursor)
                
                # 7. 인덱스 생성
                self._create_performance_indexes(cursor)
                
                # 8. 기본 데이터 삽입
                self._insert_default_data(cursor)
                
                conn.commit()
            
            self.logger.info("모니터링 시스템 마이그레이션 완료!")
            return True
            
        except Exception as e:
            self.logger.error(f"마이그레이션 실패: {e}")
            return False
    
    def _create_crawl_schedules_table(self, cursor: sqlite3.Cursor):
        """크롤링 스케줄 테이블 생성"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key TEXT NOT NULL UNIQUE,
                site_name TEXT NOT NULL,
                cron_expression TEXT DEFAULT '0 */6 * * *',  -- 6시간마다 기본
                timezone TEXT DEFAULT 'Asia/Seoul',
                enabled BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 0,  -- 0: 일반, 1: 높음, -1: 낮음
                next_run TIMESTAMP,
                last_run TIMESTAMP,
                last_success TIMESTAMP,
                last_failure TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                retry_delay INTEGER DEFAULT 300,  -- 5분
                timeout_seconds INTEGER DEFAULT 3600,  -- 1시간
                notification_enabled BOOLEAN DEFAULT 1,
                notification_threshold INTEGER DEFAULT 1,  -- 신규 데이터 1개 이상 시 알림
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system',
                notes TEXT
            )
        """)
        
        # 업데이트 트리거 생성
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_crawl_schedules_timestamp 
            AFTER UPDATE ON crawl_schedules
            BEGIN
                UPDATE crawl_schedules SET updated_at = CURRENT_TIMESTAMP 
                WHERE schedule_id = NEW.schedule_id;
            END
        """)
        
        self.logger.info("  ✓ crawl_schedules 테이블 생성 완료")
    
    def _create_notification_history_table(self, cursor: sqlite3.Cursor):
        """알림 히스토리 테이블 생성"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key TEXT NOT NULL,
                notification_type TEXT NOT NULL,  -- 'new_data', 'error', 'schedule', 'system'
                title TEXT NOT NULL,
                message TEXT,
                new_data_count INTEGER DEFAULT 0,
                urgency_level TEXT DEFAULT 'normal',  -- 'low', 'normal', 'high', 'critical'
                status TEXT DEFAULT 'sent',  -- 'pending', 'sent', 'failed', 'read'
                delivery_channels TEXT,  -- JSON: ['websocket', 'email', 'push']
                recipient TEXT,
                error_message TEXT,
                metadata TEXT,  -- JSON 추가 데이터
                read_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (site_key) REFERENCES crawl_schedules(site_key)
            )
        """)
        
        # 업데이트 트리거 생성
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_notification_history_timestamp 
            AFTER UPDATE ON notification_history
            BEGIN
                UPDATE notification_history SET updated_at = CURRENT_TIMESTAMP 
                WHERE notification_id = NEW.notification_id;
            END
        """)
        
        self.logger.info("  ✓ notification_history 테이블 생성 완료")
    
    def _create_new_data_log_table(self, cursor: sqlite3.Cursor):
        """새로운 데이터 로그 테이블 생성"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS new_data_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key TEXT NOT NULL,
                data_id TEXT NOT NULL,  -- 해당 사이트의 키 컬럼 값
                data_type TEXT DEFAULT 'record',  -- 'record', 'document', 'case', etc.
                data_title TEXT,
                data_summary TEXT,
                data_category TEXT,  -- 세목, 분야 등
                data_date TEXT,  -- 원본 데이터의 날짜 (생산일자, 결정일 등)
                crawl_session_id TEXT,  -- 크롤링 세션 식별자
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                notification_sent BOOLEAN DEFAULT 0,
                notification_id INTEGER,
                is_important BOOLEAN DEFAULT 0,  -- 중요도 마킹
                tags TEXT,  -- JSON 배열로 태그 저장
                metadata TEXT,  -- JSON 추가 메타데이터
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (site_key) REFERENCES crawl_schedules(site_key),
                FOREIGN KEY (notification_id) REFERENCES notification_history(notification_id),
                UNIQUE(site_key, data_id)  -- 사이트별 데이터 중복 방지
            )
        """)
        
        # 업데이트 트리거 생성
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_new_data_log_timestamp 
            AFTER UPDATE ON new_data_log
            BEGIN
                UPDATE new_data_log SET updated_at = CURRENT_TIMESTAMP 
                WHERE log_id = NEW.log_id;
            END
        """)
        
        self.logger.info("  ✓ new_data_log 테이블 생성 완료")
    
    def _create_system_status_table(self, cursor: sqlite3.Cursor):
        """시스템 상태 테이블 생성"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_status (
                status_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key TEXT NOT NULL,
                component_type TEXT DEFAULT 'crawler',  -- 'crawler', 'scheduler', 'notifier', 'system'
                status TEXT NOT NULL,  -- 'healthy', 'warning', 'error', 'offline', 'maintenance'
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_success TIMESTAMP,
                last_error TIMESTAMP,
                error_message TEXT,
                error_count INTEGER DEFAULT 0,
                consecutive_errors INTEGER DEFAULT 0,  -- 연속 에러 횟수
                uptime_seconds INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                memory_usage_mb REAL,
                cpu_usage_percent REAL,
                network_status TEXT,  -- 'online', 'offline', 'slow'
                health_score INTEGER DEFAULT 100,  -- 0-100 건강도 점수
                alerts_enabled BOOLEAN DEFAULT 1,
                maintenance_mode BOOLEAN DEFAULT 0,
                version TEXT,
                metadata TEXT,  -- JSON 추가 상태 정보
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (site_key) REFERENCES crawl_schedules(site_key),
                UNIQUE(site_key, component_type)
            )
        """)
        
        # 업데이트 트리거 생성
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_system_status_timestamp 
            AFTER UPDATE ON system_status
            BEGIN
                UPDATE system_status SET updated_at = CURRENT_TIMESTAMP 
                WHERE status_id = NEW.status_id;
            END
        """)
        
        self.logger.info("  ✓ system_status 테이블 생성 완료")
    
    def _create_crawl_execution_log_table(self, cursor: sqlite3.Cursor):
        """크롤링 실행 로그 테이블 생성"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_execution_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_type TEXT NOT NULL,  -- 'scheduled', 'manual', 'all_sites'
                trigger_source TEXT,  -- 'scheduler', 'manual', 'api', 'startup'
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'running',  -- 'running', 'success', 'partial_success', 'failed'
                total_sites INTEGER DEFAULT 0,
                success_sites INTEGER DEFAULT 0,
                failed_sites INTEGER DEFAULT 0,
                total_new_data_count INTEGER DEFAULT 0,
                total_duration_seconds INTEGER,
                site_results TEXT,  -- JSON: 각 사이트별 결과 상세
                error_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 업데이트 트리거 생성
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_crawl_execution_log_timestamp 
            AFTER UPDATE ON crawl_execution_log
            BEGIN
                UPDATE crawl_execution_log SET updated_at = CURRENT_TIMESTAMP 
                WHERE log_id = NEW.log_id;
            END
        """)
        
        self.logger.info("  ✓ crawl_execution_log 테이블 생성 완료")
    
    def _extend_crawl_metadata_table(self, cursor: sqlite3.Cursor):
        """기존 crawl_metadata 테이블 확장"""
        try:
            # 기존 컬럼 확인
            cursor.execute("PRAGMA table_info(crawl_metadata)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # 새로운 컬럼들 추가
            new_columns = [
                ("success_rate", "REAL DEFAULT 100.0"),
                ("avg_crawl_time", "INTEGER DEFAULT 0"),  # 평균 크롤링 시간(초)
                ("last_error", "TEXT"),
                ("error_count", "INTEGER DEFAULT 0"),
                ("data_trend", "TEXT"),  # JSON: 최근 7일간 데이터 증가 추이
                ("notification_count", "INTEGER DEFAULT 0"),
                ("is_active", "BOOLEAN DEFAULT 1"),
                ("priority", "INTEGER DEFAULT 0")
            ]
            
            for column_name, column_def in new_columns:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE crawl_metadata ADD COLUMN {column_name} {column_def}")
                        self.logger.info(f"    컬럼 추가: {column_name}")
                    except sqlite3.Error as e:
                        self.logger.warning(f"    컬럼 추가 실패 ({column_name}): {e}")
            
            self.logger.info("  ✓ crawl_metadata 테이블 확장 완료")
            
        except Exception as e:
            self.logger.error(f"crawl_metadata 테이블 확장 실패: {e}")
    
    def _create_performance_indexes(self, cursor: sqlite3.Cursor):
        """성능 최적화를 위한 인덱스 생성"""
        indexes = [
            # 크롤링 스케줄 관련
            "CREATE INDEX IF NOT EXISTS idx_crawl_schedules_next_run ON crawl_schedules(next_run, enabled)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_schedules_site_key ON crawl_schedules(site_key)",
            
            # 알림 히스토리 관련
            "CREATE INDEX IF NOT EXISTS idx_notification_history_site_key ON notification_history(site_key, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_notification_history_type ON notification_history(notification_type, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_notification_history_status ON notification_history(status)",
            
            # 새로운 데이터 로그 관련
            "CREATE INDEX IF NOT EXISTS idx_new_data_log_site_key ON new_data_log(site_key, discovered_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_new_data_log_discovered ON new_data_log(discovered_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_new_data_log_notification ON new_data_log(notification_sent, discovered_at)",
            "CREATE INDEX IF NOT EXISTS idx_new_data_log_important ON new_data_log(is_important, discovered_at DESC)",
            
            # 시스템 상태 관련
            "CREATE INDEX IF NOT EXISTS idx_system_status_site_key ON system_status(site_key, last_check DESC)",
            "CREATE INDEX IF NOT EXISTS idx_system_status_health ON system_status(status, health_score)",
            "CREATE INDEX IF NOT EXISTS idx_system_status_errors ON system_status(consecutive_errors DESC)",
            
            # 크롤링 실행 로그 관련
            "CREATE INDEX IF NOT EXISTS idx_crawl_execution_log_start_time ON crawl_execution_log(start_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_execution_log_status ON crawl_execution_log(status, start_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_execution_log_type ON crawl_execution_log(execution_type, start_time DESC)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                self.logger.warning(f"인덱스 생성 실패: {e}")
        
        self.logger.info("  ✓ 성능 인덱스 생성 완료")
    
    def _insert_default_data(self, cursor: sqlite3.Cursor):
        """기본 데이터 삽입"""
        # 사이트별 기본 스케줄 생성
        default_schedules = [
            ("tax_tribunal", "조세심판원", "0 0 */8 * *"),      # 8시간마다
            ("nts_authority", "국세청 유권해석", "0 0 */6 * *"),  # 6시간마다
            ("nts_precedent", "국세청 판례", "0 0 */12 * *"),    # 12시간마다
            ("moef", "기획재정부", "0 0 */6 * *"),               # 6시간마다
            ("mois", "행정안전부", "0 0 */8 * *"),               # 8시간마다
            ("bai", "감사원", "0 0 */12 * *")                   # 12시간마다
        ]
        
        for site_key, site_name, cron_expr in default_schedules:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO crawl_schedules 
                    (site_key, site_name, cron_expression, enabled, priority, notification_threshold)
                    VALUES (?, ?, ?, 1, 0, 1)
                """, (site_key, site_name, cron_expr))
                
                # 시스템 상태 초기화
                cursor.execute("""
                    INSERT OR IGNORE INTO system_status 
                    (site_key, component_type, status, health_score)
                    VALUES (?, 'crawler', 'healthy', 100)
                """, (site_key,))
                
            except sqlite3.Error as e:
                self.logger.warning(f"기본 데이터 삽입 실패 ({site_key}): {e}")
        
        self.logger.info("  ✓ 기본 데이터 삽입 완료")
    
    def _create_backup(self) -> str:
        """데이터베이스 백업 생성"""
        if not os.path.exists(self.db_path):
            return ""
        
        backup_dir = "data/backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"tax_data_backup_{timestamp}.db")
        
        # 파일 복사
        import shutil
        shutil.copy2(self.db_path, backup_path)
        
        return backup_path
    
    def get_migration_status(self) -> Dict[str, Any]:
        """마이그레이션 상태 확인"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 테이블 존재 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                required_tables = {
                    'crawl_schedules', 'notification_history', 
                    'new_data_log', 'system_status', 'crawl_execution_log'
                }
                
                missing_tables = required_tables - existing_tables
                
                status = {
                    "migration_needed": len(missing_tables) > 0,
                    "existing_tables": list(existing_tables),
                    "missing_tables": list(missing_tables),
                    "database_exists": True
                }
                
                return status
                
        except Exception as e:
            return {
                "migration_needed": True,
                "error": str(e),
                "database_exists": False
            }
    
    def rollback_migration(self, backup_path: str) -> bool:
        """마이그레이션 롤백"""
        try:
            if os.path.exists(backup_path):
                import shutil
                shutil.copy2(backup_path, self.db_path)
                self.logger.info(f"마이그레이션 롤백 완료: {backup_path} -> {self.db_path}")
                return True
            else:
                self.logger.error(f"백업 파일 없음: {backup_path}")
                return False
        except Exception as e:
            self.logger.error(f"롤백 실패: {e}")
            return False


def main():
    """마이그레이션 실행 메인 함수"""
    migration = DatabaseMigration()
    
    # 마이그레이션 상태 확인
    status = migration.get_migration_status()
    print("=== 마이그레이션 상태 ===")
    print(f"마이그레이션 필요: {status['migration_needed']}")
    print(f"기존 테이블: {status.get('existing_tables', [])}")
    print(f"누락된 테이블: {status.get('missing_tables', [])}")
    
    if status['migration_needed']:
        print("\n마이그레이션을 시작합니다...")
        success = migration.migrate_to_monitoring_system()
        
        if success:
            print("✅ 마이그레이션 성공!")
        else:
            print("❌ 마이그레이션 실패!")
            return False
    else:
        print("✅ 마이그레이션이 이미 완료되었습니다.")
    
    return True


if __name__ == "__main__":
    main()