"""
설정 라우터

엔드포인트:
- GET /settings : 설정 페이지
- GET /api/email-settings : 이메일 설정 조회
- POST /api/email-settings : 이메일 설정 저장
- POST /api/email-settings/test : 테스트 이메일 발송
- GET /api/tunnel-status : 터널 상태 조회
- POST /api/tunnel/start/{tunnel_type} : 터널 시작
- POST /api/tunnel/stop/{tunnel_type} : 터널 중지
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
import sqlite3
import json
import re


def create_settings_router(
    templates: Jinja2Templates,
    repository: Any,
    notification_service: Optional[Any] = None
) -> APIRouter:
    """
    설정 라우터 생성

    Args:
        templates: Jinja2 템플릿 엔진
        repository: 데이터 저장소
        notification_service: 알림 서비스 (선택)
    """
    router = APIRouter()

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """설정 페이지"""
        return templates.TemplateResponse("settings.html", {"request": request})

    @router.get("/api/email-settings")
    async def get_email_settings():
        """이메일 설정 조회"""
        try:
            with sqlite3.connect(repository.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM email_settings
                    ORDER BY is_primary DESC, created_at
                """)

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                settings = []
                for row in rows:
                    setting = dict(zip(columns, row))
                    setting.pop('encrypted_password', None)

                    if setting.get('notification_types'):
                        setting['notification_types'] = json.loads(setting['notification_types'])

                    settings.append(setting)

                return settings

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"이메일 설정 조회 실패: {str(e)}")

    @router.post("/api/email-settings")
    async def save_email_settings(request: Request):
        """이메일 설정 저장"""
        try:
            data = await request.json()

            required_fields = ['email_address', 'smtp_server', 'smtp_port']
            for field in required_fields:
                if not data.get(field):
                    raise HTTPException(status_code=400, detail=f"{field} 필드가 필요합니다")

            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email_address']):
                raise HTTPException(status_code=400, detail="올바른 이메일 주소를 입력해주세요")

            try:
                port = int(data['smtp_port'])
                if port < 1 or port > 65535:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="올바른 포트 번호를 입력해주세요 (1-65535)")

            with sqlite3.connect(repository.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT setting_id FROM email_settings WHERE email_address = ?",
                             (data['email_address'],))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute("""
                        UPDATE email_settings
                        SET smtp_server = ?, smtp_port = ?, smtp_username = ?, use_tls = ?,
                            is_active = ?, notification_types = ?, min_data_threshold = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email_address = ?
                    """, (
                        data['smtp_server'],
                        port,
                        data.get('smtp_username', ''),
                        data.get('use_tls', True),
                        data.get('is_active', True),
                        data.get('notification_types', '["new_data"]'),
                        data.get('min_data_threshold', 1),
                        data['email_address']
                    ))
                    setting_id = existing[0]
                else:
                    cursor.execute("""
                        INSERT INTO email_settings
                        (email_address, smtp_server, smtp_port, smtp_username, use_tls,
                         is_active, notification_types, min_data_threshold)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['email_address'],
                        data['smtp_server'],
                        port,
                        data.get('smtp_username', ''),
                        data.get('use_tls', True),
                        data.get('is_active', True),
                        data.get('notification_types', '["new_data"]'),
                        data.get('min_data_threshold', 1)
                    ))
                    setting_id = cursor.lastrowid

                conn.commit()

            return {
                "status": "success",
                "message": "이메일 설정이 저장되었습니다",
                "setting_id": setting_id
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"이메일 설정 저장 실패: {str(e)}")

    @router.post("/api/email-settings/test")
    async def send_test_email(request: Request):
        """테스트 이메일 발송"""
        try:
            if not notification_service:
                raise HTTPException(status_code=503, detail="알림 서비스를 사용할 수 없습니다")

            data = await request.json()
            email_address = data.get('email_address')

            if not email_address:
                raise HTTPException(status_code=400, detail="이메일 주소가 필요합니다")

            success = await notification_service.send_test_email(email_address)

            if success:
                return {
                    "status": "success",
                    "message": "테스트 이메일이 발송되었습니다"
                }
            else:
                raise HTTPException(status_code=500, detail="테스트 이메일 발송에 실패했습니다")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"테스트 이메일 발송 실패: {str(e)}")

    @router.get("/api/tunnel-status")
    async def get_tunnel_status():
        """터널 상태 조회 (LocalTunnel/ngrok)"""
        try:
            import subprocess

            tunnel_status = {
                "localtunnel": {"status": "unknown", "url": None},
                "ngrok": {"status": "unknown", "url": None}
            }

            try:
                result = subprocess.run(['systemctl', '--user', 'is-active', 'localtunnel'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip() == 'active':
                    tunnel_status["localtunnel"]["status"] = "active"
                    tunnel_status["localtunnel"]["url"] = "https://taxupdater-monitor.loca.lt"
                else:
                    tunnel_status["localtunnel"]["status"] = "inactive"
            except Exception as e:
                tunnel_status["localtunnel"]["status"] = f"error: {str(e)}"

            try:
                result = subprocess.run(['pgrep', '-x', 'ngrok'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    tunnel_status["ngrok"]["status"] = "active"
                    try:
                        import requests
                        response = requests.get("http://localhost:4040/api/tunnels", timeout=3)
                        if response.status_code == 200:
                            tunnels = response.json().get('tunnels', [])
                            if tunnels:
                                tunnel_status["ngrok"]["url"] = tunnels[0].get('public_url')
                    except Exception:
                        pass
                else:
                    tunnel_status["ngrok"]["status"] = "inactive"
            except Exception as e:
                tunnel_status["ngrok"]["status"] = f"error: {str(e)}"

            return tunnel_status

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 상태 확인 실패: {str(e)}")

    @router.post("/api/tunnel/start/{tunnel_type}")
    async def start_tunnel(tunnel_type: str):
        """터널 시작 (localtunnel/ngrok)"""
        try:
            import subprocess

            if tunnel_type == "localtunnel":
                result = subprocess.run(['systemctl', '--user', 'start', 'localtunnel'],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {"message": "LocalTunnel이 시작되었습니다", "success": True}
                else:
                    raise HTTPException(status_code=500, detail=f"LocalTunnel 시작 실패: {result.stderr}")

            elif tunnel_type == "ngrok":
                result = subprocess.run(['systemctl', '--user', 'start', 'ngrok'],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {"message": "ngrok이 시작되었습니다", "success": True}
                else:
                    raise HTTPException(status_code=500, detail=f"ngrok 시작 실패: {result.stderr}")
            else:
                raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 시작 실패: {str(e)}")

    @router.post("/api/tunnel/stop/{tunnel_type}")
    async def stop_tunnel(tunnel_type: str):
        """터널 중지 (localtunnel/ngrok)"""
        try:
            import subprocess

            if tunnel_type == "localtunnel":
                result = subprocess.run(['systemctl', '--user', 'stop', 'localtunnel'],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {"message": "LocalTunnel이 중지되었습니다", "success": True}
                else:
                    raise HTTPException(status_code=500, detail=f"LocalTunnel 중지 실패: {result.stderr}")

            elif tunnel_type == "ngrok":
                result = subprocess.run(['systemctl', '--user', 'stop', 'ngrok'],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {"message": "ngrok이 중지되었습니다", "success": True}
                else:
                    raise HTTPException(status_code=500, detail=f"ngrok 중지 실패: {result.stderr}")
            else:
                raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 중지 실패: {str(e)}")

    return router
