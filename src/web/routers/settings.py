import json
import os
import re
import sqlite3

from fastapi import APIRouter, HTTPException, Request

from src.web.context import WebAppContext


def create_settings_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()
    logger = context.logger

    @router.get("/api/ntfy-settings")
    async def get_ntfy_settings():
        try:
            ntfy_url = context.notification_service._get_ntfy_url()
            return {
                "enabled": context.notification_service.notification_settings.get("ntfy_enabled", False),
                "configured": bool(ntfy_url),
                "topic": os.getenv("NTFY_TOPIC", ""),
                "server_url": os.getenv("NTFY_SERVER_URL", "https://ntfy.sh"),
                "explicit_url_configured": bool(os.getenv("NTFY_URL")),
                "item_limit": context.notification_service._ntfy_item_limit(),
                "dashboard_url": os.getenv("DASHBOARD_URL", "http://localhost:8001"),
                "click_url": os.getenv("NTFY_CLICK_URL", ""),
                "auth_configured": bool(
                    os.getenv("NTFY_TOKEN")
                    or (os.getenv("NTFY_USERNAME") and os.getenv("NTFY_PASSWORD"))
                ),
            }
        except Exception as e:
            logger.error(f"ntfy 설정 조회 실패: {e}")
            raise HTTPException(status_code=500, detail=f"ntfy 설정 조회 실패: {str(e)}")

    @router.get("/api/email-settings")
    async def get_email_settings():
        try:
            with sqlite3.connect(context.repository.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM email_settings
                    ORDER BY is_primary DESC, created_at
                    """
                )

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                settings = []
                for row in rows:
                    setting = dict(zip(columns, row))
                    setting.pop("encrypted_password", None)

                    if setting.get("notification_types"):
                        setting["notification_types"] = json.loads(setting["notification_types"])

                    settings.append(setting)

                return settings
        except Exception as e:
            logger.error(f"이메일 설정 조회 실패: {e}")
            raise HTTPException(status_code=500, detail=f"이메일 설정 조회 실패: {str(e)}")

    @router.post("/api/email-settings")
    async def save_email_settings(request: Request):
        try:
            data = await request.json()

            required_fields = ["email_address", "smtp_server", "smtp_port"]
            for field in required_fields:
                if not data.get(field):
                    raise HTTPException(status_code=400, detail=f"{field} 필드가 필요합니다")

            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, data["email_address"]):
                raise HTTPException(status_code=400, detail="올바른 이메일 주소를 입력해주세요")

            try:
                port = int(data["smtp_port"])
                if port < 1 or port > 65535:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="올바른 포트 번호를 입력해주세요 (1-65535)")

            with sqlite3.connect(context.repository.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT setting_id FROM email_settings WHERE email_address = ?",
                    (data["email_address"],),
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        """
                        UPDATE email_settings
                        SET smtp_server = ?, smtp_port = ?, smtp_username = ?, use_tls = ?,
                            is_active = ?, notification_types = ?, min_data_threshold = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email_address = ?
                        """,
                        (
                            data["smtp_server"],
                            port,
                            data.get("smtp_username", ""),
                            data.get("use_tls", True),
                            data.get("is_active", True),
                            data.get("notification_types", '["new_data"]'),
                            data.get("min_data_threshold", 1),
                            data["email_address"],
                        ),
                    )
                    setting_id = existing[0]
                else:
                    cursor.execute(
                        """
                        INSERT INTO email_settings
                        (email_address, smtp_server, smtp_port, smtp_username, use_tls,
                         is_active, notification_types, min_data_threshold)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data["email_address"],
                            data["smtp_server"],
                            port,
                            data.get("smtp_username", ""),
                            data.get("use_tls", True),
                            data.get("is_active", True),
                            data.get("notification_types", '["new_data"]'),
                            data.get("min_data_threshold", 1),
                        ),
                    )
                    setting_id = cursor.lastrowid

                conn.commit()

            return {
                "status": "success",
                "message": "이메일 설정이 저장되었습니다",
                "setting_id": setting_id,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"이메일 설정 저장 실패: {e}")
            raise HTTPException(status_code=500, detail=f"이메일 설정 저장 실패: {str(e)}")

    @router.post("/api/email-settings/test")
    async def send_test_email(request: Request):
        try:
            data = await request.json()
            email_address = data.get("email_address")

            if not email_address:
                raise HTTPException(status_code=400, detail="이메일 주소가 필요합니다")

            success = await context.notification_service.send_test_email(email_address)

            if success:
                return {
                    "status": "success",
                    "message": "테스트 이메일이 발송되었습니다",
                }
            raise HTTPException(status_code=500, detail="테스트 이메일 발송에 실패했습니다")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"테스트 이메일 발송 실패: {e}")
            raise HTTPException(status_code=500, detail=f"테스트 이메일 발송 실패: {str(e)}")

    return router
