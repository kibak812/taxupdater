"""
알림 서비스
새로운 데이터 발견, 에러, 시스템 상태 등에 대한 알림 관리
"""

import os
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config.logging_config import get_logger


@dataclass
class NotificationData:
    """알림 데이터 구조"""
    site_key: str
    notification_type: str  # 'new_data', 'error', 'schedule', 'system'
    title: str
    message: str
    urgency_level: str = 'normal'  # 'low', 'normal', 'high', 'critical'
    new_data_count: int = 0
    delivery_channels: List[str] = None
    metadata: Dict[str, Any] = None
    expires_at: datetime = None


class NotificationService:
    """알림 서비스 클래스"""
    
    def __init__(self, db_path: str = "data/tax_data.db", websocket_manager=None):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        self.websocket_manager = websocket_manager
        
        # 사이트 이름 매핑
        self.site_names = {
            "tax_tribunal": "조세심판원",
            "nts_authority": "국세청 유권해석",
            "nts_precedent": "국세청 판례",
            "moef": "기획재정부",
            "mois": "행정안전부",
            "bai": "감사원"
        }
        
        # 알림 설정
        self.notification_settings = {
            'email_enabled': False,  # 이메일 알림 (추후 구현)
            'websocket_enabled': True,  # WebSocket 알림
            'push_enabled': True,  # 브라우저 푸시 알림
            'min_interval': 300,  # 최소 알림 간격 (초)
            'max_daily_notifications': 50  # 일일 최대 알림 수
        }
        
        # 최근 알림 캐시 (스팸 방지)
        self.recent_notifications = {}
        
        self.logger.info("알림 서비스 초기화 완료")
    
    async def send_new_data_notification(self, site_key: str, new_data_count: int, 
                                       session_id: str = None) -> bool:
        """새로운 데이터 발견 알림 발송"""
        try:
            # 알림 임계값 확인
            threshold = await self._get_notification_threshold(site_key)
            if new_data_count < threshold:
                self.logger.info(f"알림 임계값 미달: {site_key} ({new_data_count} < {threshold})")
                return True
            
            # 중복 알림 방지
            if await self._check_duplicate_notification(site_key, 'new_data'):
                self.logger.info(f"중복 알림 방지: {site_key}")
                return True
            
            site_name = self.site_names.get(site_key, site_key)
            
            # 알림 데이터 구성
            notification = NotificationData(
                site_key=site_key,
                notification_type='new_data',
                title=f"새로운 데이터 발견: {site_name}",
                message=f"{site_name}에서 {new_data_count}개의 새로운 데이터가 발견되었습니다.",
                urgency_level='normal' if new_data_count < 10 else 'high',
                new_data_count=new_data_count,
                delivery_channels=['websocket', 'push'],
                metadata={
                    'session_id': session_id,
                    'site_name': site_name
                },
                expires_at=datetime.now() + timedelta(hours=24)
            )
            
            # 알림 저장 및 발송
            notification_id = await self._save_notification(notification)
            
            if notification_id:
                await self._send_notification(notification, notification_id)
                
                # 새로운 데이터 로그 업데이트
                await self._update_new_data_log(site_key, notification_id)
                
                self.logger.info(f"새로운 데이터 알림 발송: {site_key} ({new_data_count}개)")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"새로운 데이터 알림 발송 실패: {e}")
            return False
    
    async def send_error_notification(self, site_key: str, error_message: str, 
                                    session_id: str = None) -> bool:
        """에러 알림 발송"""
        try:
            # 에러 알림 빈도 제한
            if await self._check_error_rate_limit(site_key):
                self.logger.info(f"에러 알림 빈도 제한: {site_key}")
                return True
            
            site_name = self.site_names.get(site_key, site_key)
            
            # 알림 데이터 구성
            notification = NotificationData(
                site_key=site_key,
                notification_type='error',
                title=f"크롤링 오류: {site_name}",
                message=f"{site_name} 크롤링 중 오류가 발생했습니다: {error_message[:100]}...",
                urgency_level='high',
                delivery_channels=['websocket'],
                metadata={
                    'session_id': session_id,
                    'site_name': site_name,
                    'full_error_message': error_message
                },
                expires_at=datetime.now() + timedelta(hours=12)
            )
            
            # 알림 저장 및 발송
            notification_id = await self._save_notification(notification)
            
            if notification_id:
                await self._send_notification(notification, notification_id)
                self.logger.info(f"에러 알림 발송: {site_key}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"에러 알림 발송 실패: {e}")
            return False
    
    async def send_system_notification(self, message: str, urgency_level: str = 'normal',
                                     notification_type: str = 'system') -> bool:
        """시스템 알림 발송"""
        try:
            notification = NotificationData(
                site_key='system',
                notification_type=notification_type,
                title="시스템 알림",
                message=message,
                urgency_level=urgency_level,
                delivery_channels=['websocket'],
                metadata={
                    'system_message': True
                },
                expires_at=datetime.now() + timedelta(hours=6)
            )
            
            notification_id = await self._save_notification(notification)
            
            if notification_id:
                await self._send_notification(notification, notification_id)
                self.logger.info(f"시스템 알림 발송: {message}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"시스템 알림 발송 실패: {e}")
            return False
    
    async def get_notifications(self, site_key: str = None, 
                              notification_type: str = None,
                              limit: int = 50, 
                              unread_only: bool = False) -> List[Dict[str, Any]]:
        """알림 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 쿼리 구성
                where_conditions = []
                params = []
                
                if site_key:
                    where_conditions.append("site_key = ?")
                    params.append(site_key)
                
                if notification_type:
                    where_conditions.append("notification_type = ?")
                    params.append(notification_type)
                
                if unread_only:
                    where_conditions.append("read_at IS NULL")
                
                # 만료되지 않은 알림만 조회
                where_conditions.append("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)")
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                query = f"""
                    SELECT notification_id, site_key, notification_type, title, message,
                           new_data_count, urgency_level, status, delivery_channels,
                           metadata, read_at, created_at, expires_at
                    FROM notification_history 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                
                params.append(limit)
                cursor.execute(query, params)
                
                columns = [desc[0] for desc in cursor.description]
                notifications = []
                
                for row in cursor.fetchall():
                    notification = dict(zip(columns, row))
                    
                    # JSON 필드 파싱
                    if notification['delivery_channels']:
                        notification['delivery_channels'] = json.loads(notification['delivery_channels'])
                    if notification['metadata']:
                        notification['metadata'] = json.loads(notification['metadata'])
                    
                    notifications.append(notification)
                
                return notifications
                
        except Exception as e:
            self.logger.error(f"알림 조회 실패: {e}")
            return []
    
    async def mark_notification_read(self, notification_id: int) -> bool:
        """알림 읽음 처리"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE notification_history 
                    SET read_at = CURRENT_TIMESTAMP, status = 'read'
                    WHERE notification_id = ?
                """, (notification_id,))
                
                if conn.total_changes > 0:
                    self.logger.info(f"알림 읽음 처리: {notification_id}")
                    return True
                else:
                    self.logger.warning(f"알림 읽음 처리 실패: {notification_id} (존재하지 않음)")
                    return False
                    
        except Exception as e:
            self.logger.error(f"알림 읽음 처리 실패: {e}")
            return False
    
    async def _save_notification(self, notification: NotificationData) -> Optional[int]:
        """알림을 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO notification_history 
                    (site_key, notification_type, title, message, new_data_count, 
                     urgency_level, status, delivery_channels, metadata, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """, (
                    notification.site_key,
                    notification.notification_type,
                    notification.title,
                    notification.message,
                    notification.new_data_count,
                    notification.urgency_level,
                    json.dumps(notification.delivery_channels or []),
                    json.dumps(notification.metadata or {}),
                    notification.expires_at.isoformat() if notification.expires_at else None
                ))
                
                notification_id = cursor.lastrowid
                
                # 알림 수 업데이트
                cursor.execute("""
                    UPDATE crawl_metadata 
                    SET notification_count = notification_count + 1
                    WHERE site_key = ?
                """, (notification.site_key,))
                
                return notification_id
                
        except Exception as e:
            self.logger.error(f"알림 저장 실패: {e}")
            return None
    
    async def _send_notification(self, notification: NotificationData, notification_id: int):
        """실제 알림 발송"""
        try:
            channels = notification.delivery_channels or []
            success_channels = []
            
            # WebSocket 알림
            if 'websocket' in channels:
                if await self._send_websocket_notification(notification, notification_id):
                    success_channels.append('websocket')
            
            # 상태 업데이트
            status = 'sent' if success_channels else 'failed'
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE notification_history 
                    SET status = ?, delivery_channels = ?
                    WHERE notification_id = ?
                """, (status, json.dumps(success_channels), notification_id))
            
            self.logger.info(f"알림 발송 완료: {notification_id} ({', '.join(success_channels)})")
            
        except Exception as e:
            self.logger.error(f"알림 발송 실패: {e}")
    
    async def _send_websocket_notification(self, notification: NotificationData, 
                                         notification_id: int) -> bool:
        """WebSocket 알림 발송"""
        try:
            # WebSocket 메시지 구성
            message = {
                'type': 'notification',
                'notification_id': notification_id,
                'site_key': notification.site_key,
                'notification_type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'urgency_level': notification.urgency_level,
                'new_data_count': notification.new_data_count,
                'metadata': notification.metadata,
                'timestamp': datetime.now().isoformat()
            }
            
            # WebSocket 매니저를 통해 실제 발송
            if self.websocket_manager:
                await self.websocket_manager.broadcast(message)
                self.logger.info(f"WebSocket 알림 발송 성공: {notification_id}")
                return True
            else:
                self.logger.warning("WebSocket 매니저가 설정되지 않음")
                return False
            
        except Exception as e:
            self.logger.error(f"WebSocket 알림 발송 실패: {e}")
            return False
    
    async def _get_notification_threshold(self, site_key: str) -> int:
        """사이트별 알림 임계값 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT notification_threshold FROM crawl_schedules 
                    WHERE site_key = ?
                """, (site_key,))
                
                result = cursor.fetchone()
                return result[0] if result else 1
                
        except Exception as e:
            self.logger.error(f"알림 임계값 조회 실패: {e}")
            return 1
    
    async def _check_duplicate_notification(self, site_key: str, 
                                          notification_type: str) -> bool:
        """중복 알림 체크"""
        try:
            cache_key = f"{site_key}_{notification_type}"
            
            # 메모리 캐시 체크
            if cache_key in self.recent_notifications:
                last_sent = self.recent_notifications[cache_key]
                if datetime.now() - last_sent < timedelta(seconds=self.notification_settings['min_interval']):
                    return True
            
            # 캐시 업데이트
            self.recent_notifications[cache_key] = datetime.now()
            return False
            
        except Exception as e:
            self.logger.error(f"중복 알림 체크 실패: {e}")
            return False
    
    async def _check_error_rate_limit(self, site_key: str) -> bool:
        """에러 알림 빈도 제한 체크"""
        try:
            # 최근 1시간 내 에러 알림 수 확인
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM notification_history 
                    WHERE site_key = ? AND notification_type = 'error' 
                    AND created_at >= ?
                """, (site_key, cutoff_time.isoformat()))
                
                count = cursor.fetchone()[0]
                
                # 1시간 내 3개 이상의 에러 알림이면 제한
                return count >= 3
                
        except Exception as e:
            self.logger.error(f"에러 알림 빈도 제한 체크 실패: {e}")
            return False
    
    async def _update_new_data_log(self, site_key: str, notification_id: int):
        """새로운 데이터 로그의 알림 정보 업데이트"""
        try:
            # 최근 5분 내 발견된 데이터 업데이트
            cutoff_time = datetime.now() - timedelta(minutes=5)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE new_data_log 
                    SET notification_sent = 1, notification_id = ?
                    WHERE site_key = ? AND discovered_at >= ? 
                    AND notification_sent = 0
                """, (notification_id, site_key, cutoff_time.isoformat()))
                
                updated_count = conn.total_changes
                self.logger.info(f"새로운 데이터 로그 업데이트: {updated_count}개")
                
        except Exception as e:
            self.logger.error(f"새로운 데이터 로그 업데이트 실패: {e}")
    
    def create_monitoring_status_report(self, repository_stats: Dict[str, Any]) -> str:
        """
        전체 모니터링 상태 보고서 생성
        
        Args:
            repository_stats: 저장소 통계 정보
            
        Returns:
            모니터링 상태 보고서
        """
        total_records = sum(stats.get('total_count', 0) for stats in repository_stats.values())
        
        site_status = []
        for site_key, stats in repository_stats.items():
            site_name = self.site_names.get(site_key, site_key)
            count = stats.get('total_count', 0)
            last_update = stats.get('last_updated', '없음')
            
            if isinstance(last_update, str) and last_update != '없음':
                last_update = f"최근 업데이트: {last_update}"
            elif last_update and last_update != '없음':
                last_update = f"최근 업데이트: {last_update.strftime('%Y-%m-%d %H:%M')}"
            else:
                last_update = "업데이트 없음"
            
            site_status.append(f"  • {site_name}: {count:,}건 ({last_update})")
        
        report = f"""📊 데이터 모니터링 현황 보고서

📈 전체 수집 현황:
  • 총 수집 데이터: {total_records:,}건
  • 모니터링 사이트: {len(repository_stats)}개
  • 보고서 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 사이트별 현황:
{chr(10).join(site_status)}

🔍 모니터링 목적:
  • 새로운 법령 해석 및 판례의 신속한 탐지
  • 업로드 누락 방지를 위한 지속적 감시
  • 데이터 무결성 보장

✅ 시스템 상태: 정상 작동 중"""

        return report
    
    def create_error_alert(self, site_key: str, error_message: str) -> str:
        """
        에러 알림 메시지 생성
        
        Args:
            site_key: 사이트 키
            error_message: 에러 메시지
            
        Returns:
            포맷팅된 에러 알림 메시지
        """
        site_name = self.site_names.get(site_key, site_key)
        
        return f"""⚠️ 크롤링 오류 발생

🌐 사이트: {site_name}
❌ 오류 내용: {error_message}
🕒 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📝 조치 사항:
- 사이트 접속 가능 여부 확인
- 네트워크 연결 상태 점검
- 로그 파일 검토

시스템이 자동으로 재시도를 수행합니다."""