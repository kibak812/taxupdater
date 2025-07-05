#!/usr/bin/env python3
"""
Fly.io 배포 환경 데이터베이스 스키마 수정 스크립트
누락된 컬럼과 테이블을 안전하게 추가
"""

import os
import sys
import sqlite3
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config.logging_config import get_logger

def fix_database_schema(db_path: str = "data/tax_data.db"):
    """데이터베이스 스키마 수정"""
    logger = get_logger(__name__)
    
    try:
        # 데이터베이스 연결
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("🔧 데이터베이스 스키마 수정 시작...")
            
            # 1. crawl_schedules 테이블에 누락된 컬럼 추가
            try:
                cursor.execute("PRAGMA table_info(crawl_schedules)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                
                required_cols = [
                    ("avg_crawl_time", "INTEGER DEFAULT 0"),
                    ("consecutive_errors", "INTEGER DEFAULT 0"),
                ]
                
                for col_name, col_def in required_cols:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE crawl_schedules ADD COLUMN {col_name} {col_def}")
                        print(f"  ✓ crawl_schedules.{col_name} 컬럼 추가")
                        
            except sqlite3.Error as e:
                print(f"  ⚠️ crawl_schedules 컬럼 추가 중 오류: {e}")
            
            # 2. NotificationService에서 필요한 메서드 확인용 테스트 데이터 추가
            try:
                # 시스템 상태 테이블에 기본 데이터가 있는지 확인
                cursor.execute("SELECT COUNT(*) FROM system_status")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    # 기본 시스템 상태 데이터 추가
                    sites = ['tax_tribunal', 'nts_authority', 'nts_precedent', 'moef', 'mois', 'bai']
                    for site in sites:
                        cursor.execute("""
                            INSERT OR IGNORE INTO system_status 
                            (site_key, component_type, status, health_score, last_check)
                            VALUES (?, 'crawler', 'healthy', 100, CURRENT_TIMESTAMP)
                        """, (site,))
                    print(f"  ✓ system_status 기본 데이터 {len(sites)}개 추가")
                    
            except sqlite3.Error as e:
                print(f"  ⚠️ system_status 데이터 추가 중 오류: {e}")
            
            # 3. crawl_metadata 테이블 필수 컬럼 확인
            try:
                cursor.execute("PRAGMA table_info(crawl_metadata)")
                existing_meta_cols = {row[1] for row in cursor.fetchall()}
                
                required_meta_cols = [
                    ("success_rate", "REAL DEFAULT 100.0"),
                    ("avg_crawl_time", "INTEGER DEFAULT 0"),
                    ("error_count", "INTEGER DEFAULT 0"),
                    ("notification_count", "INTEGER DEFAULT 0"),
                ]
                
                for col_name, col_def in required_meta_cols:
                    if col_name not in existing_meta_cols:
                        cursor.execute(f"ALTER TABLE crawl_metadata ADD COLUMN {col_name} {col_def}")
                        print(f"  ✓ crawl_metadata.{col_name} 컬럼 추가")
                        
            except sqlite3.Error as e:
                print(f"  ⚠️ crawl_metadata 컬럼 추가 중 오류: {e}")
            
            conn.commit()
            print("✅ 데이터베이스 스키마 수정 완료")
            return True
            
    except Exception as e:
        print(f"❌ 데이터베이스 스키마 수정 실패: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🏥 Fly.io 배포 환경 데이터베이스 복구 스크립트")
    print("=" * 50)
    
    # 1. 데이터베이스 경로 확인
    db_path = "data/tax_data.db"
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일 없음: {db_path}")
        return 1
    
    print(f"📂 데이터베이스 경로: {db_path}")
    print(f"📊 파일 크기: {os.path.getsize(db_path)} bytes")
    
    # 2. 마이그레이션 실행
    from src.database.migrations import DatabaseMigration
    migration = DatabaseMigration(db_path)
    
    status = migration.get_migration_status()
    print(f"🔍 마이그레이션 상태: {status}")
    
    if status['migration_needed']:
        print("🚀 마이그레이션 실행 중...")
        success = migration.migrate_to_monitoring_system()
        if not success:
            print("❌ 마이그레이션 실패")
            return 1
    
    # 3. 스키마 수정
    if not fix_database_schema(db_path):
        return 1
    
    # 4. 서비스 테스트
    print("\n🧪 서비스 연결 테스트...")
    try:
        from src.services.scheduler_service import SchedulerService
        from src.services.notification_service import NotificationService
        
        # SchedulerService 테스트
        scheduler = SchedulerService(db_path=db_path)
        schedule_status = scheduler.get_schedule_status()
        print(f"  ✓ SchedulerService 연결 성공")
        
        # NotificationService 테스트  
        notification = NotificationService(db_path=db_path)
        print(f"  ✓ NotificationService 연결 성공")
        
        print("✅ 모든 서비스 연결 테스트 통과")
        return 0
        
    except Exception as e:
        print(f"❌ 서비스 연결 테스트 실패: {e}")
        return 1

if __name__ == "__main__":
    exit(main())