"""
알림 라우터

엔드포인트:
- GET /api/notifications : 알림 목록 조회
- POST /api/notifications/{notification_id}/read : 알림 읽음 처리
- GET /api/notifications/stats : 알림 통계
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional


def create_notification_router(
    notification_service: Optional[Any] = None
) -> APIRouter:
    """
    알림 라우터 생성

    Args:
        notification_service: 알림 서비스
    """
    router = APIRouter()

    def check_notification_service():
        if not notification_service:
            raise HTTPException(status_code=503, detail="알림 서비스를 사용할 수 없습니다")

    @router.get("/api/notifications")
    async def get_notifications(
        site_key: str = None,
        notification_type: str = None,
        limit: int = 50,
        unread_only: bool = False
    ):
        """알림 목록 조회"""
        try:
            check_notification_service()

            notifications = await notification_service.get_notifications(
                site_key, notification_type, limit, unread_only
            )
            return {
                "notifications": notifications,
                "total_count": len(notifications)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 조회 실패: {str(e)}")

    @router.post("/api/notifications/{notification_id}/read")
    async def mark_notification_read(notification_id: int):
        """알림 읽음 처리"""
        try:
            check_notification_service()

            success = await notification_service.mark_notification_read(notification_id)

            if success:
                return {
                    "status": "success",
                    "message": "알림이 읽음 처리되었습니다"
                }
            else:
                raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 읽음 처리 실패: {str(e)}")

    @router.get("/api/notifications/stats")
    async def get_notification_stats(site_key: str = None):
        """알림 통계 조회"""
        try:
            check_notification_service()

            stats = await notification_service.get_notification_stats(site_key)
            return stats
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 통계 조회 실패: {str(e)}")

    return router
