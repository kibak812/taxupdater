#!/usr/bin/env python3
"""
Fly.io 배포 환경에서 데이터베이스 마이그레이션 상태 확인 및 자동 실행
"""

import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.migrations import DatabaseMigration

def main():
    """마이그레이션 확인 및 실행"""
    print("🔍 데이터베이스 마이그레이션 상태 확인 중...")
    
    # 마이그레이션 인스턴스 생성
    migration = DatabaseMigration()
    
    # 현재 상태 확인
    status = migration.get_migration_status()
    
    print(f"📊 마이그레이션 상태:")
    print(f"  • 마이그레이션 필요: {status['migration_needed']}")
    print(f"  • 기존 테이블: {len(status.get('existing_tables', []))}개")
    print(f"  • 누락된 테이블: {status.get('missing_tables', [])}")
    
    if status['migration_needed']:
        print("\n🚀 마이그레이션 시작...")
        success = migration.migrate_to_monitoring_system()
        
        if success:
            print("✅ 마이그레이션 성공! 모니터링 시스템 사용 가능")
            return 0
        else:
            print("❌ 마이그레이션 실패! 수동 확인 필요")
            return 1
    else:
        print("✅ 데이터베이스가 이미 최신 상태입니다")
        return 0

if __name__ == "__main__":
    exit(main())