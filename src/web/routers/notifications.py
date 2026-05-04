from fastapi import APIRouter, HTTPException

from src.web.context import WebAppContext


def create_notification_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.get("/api/notifications")
    async def get_notifications(
        site_key: str = None,
        notification_type: str = None,
        limit: int = 50,
        unread_only: bool = False,
    ):
        try:
            notifications = await context.notification_service.get_notifications(
                site_key,
                notification_type,
                limit,
                unread_only,
            )
            return {
                "notifications": notifications,
                "total_count": len(notifications),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 조회 실패: {str(e)}")

    @router.post("/api/notifications/{notification_id}/read")
    async def mark_notification_read(notification_id: int):
        try:
            success = await context.notification_service.mark_notification_read(notification_id)

            if success:
                return {
                    "status": "success",
                    "message": "알림이 읽음 처리되었습니다",
                }
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 읽음 처리 실패: {str(e)}")

    @router.get("/api/notifications/stats")
    async def get_notification_stats(site_key: str = None):
        try:
            return await context.notification_service.get_notification_stats(site_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 통계 조회 실패: {str(e)}")

    return router
