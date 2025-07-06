#!/usr/bin/env python3
"""
알림 시스템 테스트 스크립트
새로운 데이터 발견 시 알림이 제대로 발송되는지 확인
"""

import os
import sys
import asyncio
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.notification_service import NotificationService
from src.config.logging_config import setup_logging, get_logger

# 로깅 설정
setup_logging(log_level="INFO")
logger = get_logger(__name__)


async def test_notification_system():
    """알림 시스템 테스트"""
    try:
        # NotificationService 초기화
        notification_service = NotificationService()
        
        print("\n=== 예규판례 모니터링 시스템 - 알림 기능 테스트 ===\n")
        
        # 1. 새로운 데이터 알림 테스트
        print("1. 새로운 데이터 발견 알림 테스트")
        print("-" * 50)
        
        # 테스트용 새로운 데이터 알림 발송
        sites_to_test = [
            ("tax_tribunal", 5),    # 조세심판원에서 5개 신규 데이터
            ("nts_authority", 10),  # 국세청 유권해석에서 10개 신규 데이터
            ("moef", 2),           # 기획재정부에서 2개 신규 데이터
        ]
        
        for site_key, new_count in sites_to_test:
            print(f"\n테스트: {site_key} - 신규 데이터 {new_count}개 발견")
            
            # 알림 발송
            success = await notification_service.send_new_data_notification(
                site_key=site_key,
                new_data_count=new_count,
                session_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if success:
                print(f"✅ 알림 발송 성공: {site_key}")
            else:
                print(f"❌ 알림 발송 실패: {site_key}")
        
        # 2. 알림 조회 테스트
        print("\n\n2. 발송된 알림 조회 테스트")
        print("-" * 50)
        
        # 최근 알림 조회
        notifications = await notification_service.get_notifications(limit=10)
        
        print(f"\n최근 알림 {len(notifications)}개:")
        for notif in notifications:
            print(f"\n  - ID: {notif['notification_id']}")
            print(f"    사이트: {notif['site_key']}")
            print(f"    제목: {notif['title']}")
            print(f"    메시지: {notif['message']}")
            print(f"    신규 데이터: {notif['new_data_count']}개")
            print(f"    긴급도: {notif['urgency_level']}")
            print(f"    상태: {notif['status']}")
            print(f"    발송 채널: {notif.get('delivery_channels', [])}")
            print(f"    생성시간: {notif['created_at']}")
        
        # 3. 알림 설정 확인
        print("\n\n3. 알림 설정 확인")
        print("-" * 50)
        
        # 각 사이트별 알림 임계값 확인
        import sqlite3
        with sqlite3.connect("data/tax_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT site_key, site_name, notification_threshold FROM crawl_schedules")
            thresholds = cursor.fetchall()
            
            print("\n사이트별 알림 임계값:")
            for site_key, site_name, threshold in thresholds:
                print(f"  - {site_name} ({site_key}): {threshold}개 이상일 때 알림")
        
        # 4. 에러 알림 테스트
        print("\n\n4. 에러 알림 테스트")
        print("-" * 50)
        
        error_success = await notification_service.send_error_notification(
            site_key="test_site",
            error_message="테스트 에러: 연결 실패",
            session_id="test_error_session"
        )
        
        if error_success:
            print("✅ 에러 알림 발송 성공")
        else:
            print("❌ 에러 알림 발송 실패")
        
        # 5. 시스템 알림 테스트
        print("\n\n5. 시스템 알림 테스트")
        print("-" * 50)
        
        system_success = await notification_service.send_system_notification(
            message="알림 시스템 테스트 완료",
            urgency_level="normal"
        )
        
        if system_success:
            print("✅ 시스템 알림 발송 성공")
        else:
            print("❌ 시스템 알림 발송 실패")
        
        print("\n\n=== 알림 시스템 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"알림 시스템 테스트 실패: {e}")
        print(f"\n❌ 테스트 중 오류 발생: {e}")


if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(test_notification_system())