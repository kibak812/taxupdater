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
import yagmail
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config.logging_config import get_logger

# 환경 변수 로드
load_dotenv()


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
            "bai": "감사원",
            "scourt_major_decisions": "전국법원 주요판결"
        }
        
        # 알림 설정
        self.notification_settings = {
            'email_enabled': True,  # 이메일 알림
            'websocket_enabled': True,  # WebSocket 알림
            'push_enabled': True,  # 브라우저 푸시 알림
            'min_interval': 300,  # 최소 알림 간격 (초)
            'max_daily_notifications': 50  # 일일 최대 알림 수
        }
        
        # 최근 알림 캐시 (스팸 방지)
        self.recent_notifications = {}
        
        # ThreadPoolExecutor for blocking email operations
        self.email_executor = ThreadPoolExecutor(max_workers=3)
        
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
                delivery_channels=['websocket', 'push', 'email'],
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
            
            # Push 알림 (브라우저에서 처리하므로 성공으로 간주)
            if 'push' in channels:
                success_channels.append('push')
                self.logger.info(f"Push 알림 채널 활성화: {notification_id}")
            
            # 이메일 알림
            if 'email' in channels and self.notification_settings['email_enabled']:
                if await self._send_email_notification(notification, notification_id):
                    success_channels.append('email')
            
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
    
    async def _send_email_notification(self, notification: NotificationData, 
                                     notification_id: int) -> bool:
        """이메일 알림 발송"""
        try:
            # 활성화된 이메일 설정 조회
            email_settings = await self._get_active_email_settings()
            if not email_settings:
                self.logger.warning("활성화된 이메일 설정이 없음")
                return False
            
            # 각 이메일 주소로 발송
            success_count = 0
            for setting in email_settings:
                # 임계값 확인
                if notification.new_data_count < setting['min_data_threshold']:
                    continue
                
                # 알림 타입 확인
                notification_types = json.loads(setting['notification_types'] or '["new_data"]')
                if notification.notification_type not in notification_types:
                    continue
                
                # 이메일 발송
                if await self._send_single_email(setting, notification):
                    success_count += 1
                    # 발송 통계 업데이트
                    await self._update_email_send_stats(setting['setting_id'], success=True)
                else:
                    await self._update_email_send_stats(setting['setting_id'], success=False)
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"이메일 알림 발송 실패: {e}")
            return False
    
    async def _send_single_email(self, email_setting: dict, 
                                notification: NotificationData) -> bool:
        """단일 이메일 발송 (재시도 로직 포함)"""
        # ThreadPoolExecutor를 사용하여 블로킹 이메일 작업을 비동기로 실행
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.email_executor,
            self._sync_send_email_with_retry,
            email_setting,
            notification
        )
    
    def _sync_send_email_with_retry(self, email_setting: dict, 
                                   notification: NotificationData,
                                   max_retries: int = 3) -> bool:
        """동기 이메일 발송 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                # 환경 변수에서 이메일 비밀번호 가져오기
                email_password = os.getenv('EMAIL_PASSWORD')
                if not email_password:
                    self.logger.error("EMAIL_PASSWORD 환경 변수가 설정되지 않음")
                    return False
                
                # 표준 smtplib 사용
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                
                # 이메일 내용 구성
                subject = f"[예규판례 모니터링] {notification.title}"
                html_content = self._create_email_html_content_sync(notification)
                
                # MIME 메시지 생성
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = email_setting['smtp_username'] or email_setting['email_address']
                msg['To'] = email_setting['email_address']
                
                # HTML 본문 추가
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
                
                # SMTP 서버 연결 및 발송
                with smtplib.SMTP(email_setting['smtp_server'], int(email_setting['smtp_port'])) as server:
                    if email_setting['use_tls']:
                        server.starttls()
                    server.login(
                        email_setting['smtp_username'] or email_setting['email_address'],
                        email_password
                    )
                    server.send_message(msg)
                
                self.logger.info(f"이메일 발송 성공: {email_setting['email_address']}")
                return True
                
            except Exception as e:
                self.logger.warning(f"이메일 발송 시도 {attempt + 1}/{max_retries} 실패: {e}")
                
                if attempt < max_retries - 1:
                    # 지수 백오프로 재시도 대기
                    wait_time = 2 ** attempt
                    self.logger.info(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"이메일 발송 최종 실패 ({email_setting['email_address']}): {e}")
                    return False
        
        return False
    
    async def _create_email_html_content(self, notification: NotificationData) -> str:
        """이메일 HTML 내용 생성"""
        site_name = self.site_names.get(notification.site_key, notification.site_key)
        
        # 새로운 데이터 상세 정보 조회
        new_data_items = await self._get_recent_new_data(notification.site_key, 
                                                        notification.new_data_count)
        
        # HTML 템플릿
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Inter', -apple-system, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f3f4f6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
                .header h2 {{ margin: 0; color: #1f2937; }}
                .content {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
                .data-item {{ border-bottom: 1px solid #e5e7eb; padding: 12px 0; }}
                .data-item:last-child {{ border-bottom: none; }}
                .title {{ font-weight: 600; color: #1f2937; margin-bottom: 4px; }}
                .metadata {{ font-size: 14px; color: #6b7280; }}
                .link {{ color: #3b82f6; text-decoration: none; }}
                .link:hover {{ text-decoration: underline; }}
                .footer {{ margin-top: 20px; text-align: center; color: #6b7280; font-size: 14px; }}
                .button {{ display: inline-block; background: #3b82f6; color: white; padding: 10px 20px; 
                          border-radius: 6px; text-decoration: none; margin-top: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{notification.title}</h2>
                    <p style="margin: 8px 0 0 0; color: #6b7280;">{notification.message}</p>
                </div>
                
                <div class="content">
                    <h3>새로운 데이터 목록</h3>
        """
        
        # 데이터 항목 추가
        for item in new_data_items:
            doc_number = item.get('문서번호', '')
            title = item.get('제목', '')
            date = item.get('생산일자') or item.get('결정일', '')
            link = item.get('링크', '')
            
            html_content += f"""
                    <div class="data-item">
                        <div class="title">{title}</div>
                        <div class="metadata">
                            문서번호: {doc_number} | 날짜: {date}
                        </div>
                        {f'<a href="{link}" class="link">문서 보기 →</a>' if link else ''}
                    </div>
            """
        
        # 웹 대시보드 링크 추가
        dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8001')
        html_content += f"""
                    <div style="text-align: center; margin-top: 20px;">
                        <a href="{dashboard_url}/data/{notification.site_key}" class="button">
                            전체 데이터 보기
                        </a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>이 이메일은 예규판례 모니터링 시스템에서 자동으로 발송되었습니다.</p>
                    <p><a href="{dashboard_url}/settings" class="link">알림 설정 변경</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _create_email_html_content_sync(self, notification: NotificationData) -> str:
        """이메일 HTML 내용 생성 (동기 버전)"""
        site_name = self.site_names.get(notification.site_key, notification.site_key)
        
        # 새로운 데이터 상세 정보 조회 (동기 버전)
        new_data_items = self._get_recent_new_data_sync(notification.site_key, 
                                                       notification.new_data_count)
        
        # HTML 템플릿 (동일한 내용)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Inter', -apple-system, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f3f4f6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
                .header h2 {{ margin: 0; color: #1f2937; }}
                .content {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
                .data-item {{ border-bottom: 1px solid #e5e7eb; padding: 12px 0; }}
                .data-item:last-child {{ border-bottom: none; }}
                .title {{ font-weight: 600; color: #1f2937; margin-bottom: 4px; }}
                .metadata {{ font-size: 14px; color: #6b7280; }}
                .link {{ color: #3b82f6; text-decoration: none; }}
                .link:hover {{ text-decoration: underline; }}
                .footer {{ margin-top: 20px; text-align: center; color: #6b7280; font-size: 14px; }}
                .button {{ display: inline-block; background: #3b82f6; color: white; padding: 10px 20px; 
                          border-radius: 6px; text-decoration: none; margin-top: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{notification.title}</h2>
                    <p style="margin: 8px 0 0 0; color: #6b7280;">{notification.message}</p>
                </div>
                
                <div class="content">
                    <h3>새로운 데이터 목록</h3>
        """
        
        # 데이터 항목 추가
        for item in new_data_items:
            doc_number = item.get('문서번호', '')
            title = item.get('제목', '')
            date = item.get('생산일자') or item.get('결정일', '')
            link = item.get('링크', '')
            
            html_content += f"""
                    <div class="data-item">
                        <div class="title">{title}</div>
                        <div class="metadata">
                            문서번호: {doc_number} | 날짜: {date}
                        </div>
                        {f'<a href="{link}" class="link">문서 보기 →</a>' if link else ''}
                    </div>
            """
        
        # 웹 대시보드 링크 추가
        dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8001')
        html_content += f"""
                    <div style="text-align: center; margin-top: 20px;">
                        <a href="{dashboard_url}/data/{notification.site_key}" class="button">
                            전체 데이터 보기
                        </a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>이 이메일은 예규판례 모니터링 시스템에서 자동으로 발송되었습니다.</p>
                    <p><a href="{dashboard_url}/settings" class="link">알림 설정 변경</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    async def _get_recent_new_data(self, site_key: str, limit: int) -> List[Dict[str, Any]]:
        """최근 새로운 데이터 조회"""
        try:
            # 사이트별 테이블명 매핑
            table_mapping = {
                "tax_tribunal": "tax_tribunal_cases",
                "nts_authority": "nts_authority_interpretations",
                "nts_precedent": "nts_precedent_cases",
                "moef": "moef_tax_interpretations",
                "mois": "mois_interpretations",
                "bai": "bai_audit_claims",
                "scourt_major_decisions": "scourt_major_decisions_data"
            }
            
            table_name = table_mapping.get(site_key)
            if not table_name:
                return []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 최근 추가된 데이터 조회 (created_at 기준)
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            self.logger.error(f"새로운 데이터 조회 실패: {e}")
            return []
    
    def _get_recent_new_data_sync(self, site_key: str, limit: int) -> List[Dict[str, Any]]:
        """최근 새로운 데이터 조회 (동기 버전)"""
        try:
            # 사이트별 테이블명 매핑
            table_mapping = {
                "tax_tribunal": "tax_tribunal_cases",
                "nts_authority": "nts_authority_interpretations",
                "nts_precedent": "nts_precedent_cases",
                "moef": "moef_tax_interpretations",
                "mois": "mois_interpretations",
                "bai": "bai_audit_claims",
                "scourt_major_decisions": "scourt_major_decisions_data"
            }
            
            table_name = table_mapping.get(site_key)
            if not table_name:
                return []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 최근 추가된 데이터 조회 (created_at 기준)
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            self.logger.error(f"새로운 데이터 조회 실패: {e}")
            return []
    
    async def _get_active_email_settings(self) -> List[Dict[str, Any]]:
        """활성화된 이메일 설정 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM email_settings 
                    WHERE is_active = 1
                    ORDER BY is_primary DESC, created_at
                """)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            self.logger.error(f"이메일 설정 조회 실패: {e}")
            return []
    
    async def _update_email_send_stats(self, setting_id: int, success: bool):
        """이메일 발송 통계 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if success:
                    conn.execute("""
                        UPDATE email_settings 
                        SET send_count = send_count + 1,
                            last_sent_at = CURRENT_TIMESTAMP
                        WHERE setting_id = ?
                    """, (setting_id,))
                else:
                    conn.execute("""
                        UPDATE email_settings 
                        SET failure_count = failure_count + 1
                        WHERE setting_id = ?
                    """, (setting_id,))
                    
        except Exception as e:
            self.logger.error(f"이메일 발송 통계 업데이트 실패: {e}")
    
    async def send_test_email(self, email_address: str) -> bool:
        """테스트 이메일 발송"""
        try:
            # 테스트용 알림 데이터 생성
            test_notification = NotificationData(
                site_key='system',
                notification_type='test',
                title='테스트 이메일',
                message='이메일 설정이 올바르게 구성되었습니다.',
                urgency_level='normal',
                new_data_count=0,
                delivery_channels=['email'],
                metadata={'test': True}
            )
            
            # 이메일 설정 조회
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM email_settings 
                    WHERE email_address = ?
                """, (email_address,))
                
                columns = [desc[0] for desc in cursor.description]
                row = cursor.fetchone()
                
                if not row:
                    self.logger.error(f"이메일 설정을 찾을 수 없음: {email_address}")
                    return False
                
                email_setting = dict(zip(columns, row))
            
            # 테스트 이메일 발송
            success = await self._send_single_email(email_setting, test_notification)
            
            if success:
                # 테스트 발송 성공 기록
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE email_settings 
                        SET test_email_sent = 1
                        WHERE email_address = ?
                    """, (email_address,))
            
            return success
            
        except Exception as e:
            self.logger.error(f"테스트 이메일 발송 실패: {e}")
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
        
        report = f"""[데이터 모니터링 현황 보고서]

[전체 수집 현황]
  - 총 수집 데이터: {total_records:,}건
  - 모니터링 사이트: {len(repository_stats)}개
  - 보고서 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[사이트별 현황]
{chr(10).join(site_status)}

[모니터링 목적]
  - 새로운 법령 해석 및 판례의 신속한 탐지
  - 업로드 누락 방지를 위한 지속적 감시
  - 데이터 무결성 보장

[시스템 상태] 정상 작동 중"""

        return report
    
    async def send_all_sites_notification(self, total_new_count: int, summary: str, session_id: str = None) -> bool:
        """전체 사이트 크롤링 결과 알림 발송"""
        try:
            notification = NotificationData(
                site_key='all_sites',
                notification_type='crawl_complete',
                title=f"전체 사이트 크롤링 완료",
                message=f"전체 크롤링이 완료되었습니다. {summary}",
                urgency_level='normal' if total_new_count < 10 else 'high',
                new_data_count=total_new_count,
                delivery_channels=['websocket'],
                metadata={
                    'session_id': session_id,
                    'summary': summary,
                    'total_new_count': total_new_count
                },
                expires_at=datetime.now() + timedelta(hours=12)
            )
            
            notification_id = await self._save_notification(notification)
            
            if notification_id:
                await self._send_notification(notification, notification_id)
                self.logger.info(f"전체 사이트 크롤링 알림 발송: {total_new_count}개")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"전체 사이트 크롤링 알림 발송 실패: {e}")
            return False
    
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
        
        return f"""[크롤링 오류 발생]

사이트: {site_name}
오류 내용: {error_message}
발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[조치 사항]
- 사이트 접속 가능 여부 확인
- 네트워크 연결 상태 점검
- 로그 파일 검토

시스템이 자동으로 재시도를 수행합니다."""
    
    async def get_notification_stats(self, site_key: str = None) -> Dict[str, Any]:
        """알림 통계 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 기본 쿼리 조건
                where_conditions = []
                params = []
                
                if site_key:
                    where_conditions.append("site_key = ?")
                    params.append(site_key)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # 전체 알림 수
                cursor.execute(f"SELECT COUNT(*) FROM notification_history {where_clause}", params)
                total_notifications = cursor.fetchone()[0]
                
                # 읽지 않은 알림 수
                unread_conditions = where_conditions + ["read_at IS NULL"]
                unread_where = "WHERE " + " AND ".join(unread_conditions)
                cursor.execute(f"SELECT COUNT(*) FROM notification_history {unread_where}", params)
                unread_notifications = cursor.fetchone()[0]
                
                # 알림 타입별 통계
                cursor.execute(f"""
                    SELECT notification_type, COUNT(*) 
                    FROM notification_history {where_clause}
                    GROUP BY notification_type
                """, params)
                
                type_stats = dict(cursor.fetchall())
                
                return {
                    "total_notifications": total_notifications,
                    "unread_notifications": unread_notifications,
                    "read_notifications": total_notifications - unread_notifications,
                    "type_breakdown": type_stats,
                    "site_key": site_key
                }
                
        except Exception as e:
            self.logger.error(f"알림 통계 조회 실패: {e}")
            return {
                "total_notifications": 0,
                "unread_notifications": 0,
                "read_notifications": 0,
                "type_breakdown": {},
                "error": str(e)
            }
