from fastapi import APIRouter, HTTPException, Request

from src.web.context import WebAppContext


def create_schedule_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.get("/api/schedules")
    async def get_schedules():
        try:
            if not context.scheduler_service:
                raise HTTPException(status_code=503, detail="스케줄러 서비스를 사용할 수 없습니다")

            return context.scheduler_service.get_schedule_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 조회 실패: {str(e)}")

    @router.get("/api/schedules/{site_key}")
    async def get_site_schedule(site_key: str):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            return context.scheduler_service.get_schedule_status(site_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"사이트 스케줄 조회 실패: {str(e)}")

    @router.post("/api/schedules")
    async def create_or_update_schedule(request: Request):
        try:
            if not context.scheduler_service:
                raise HTTPException(status_code=503, detail="스케줄러 서비스를 사용할 수 없습니다")

            data = await request.json()
            site_key = data.get("site_key")
            cron_expression = data.get("cron_expression")
            enabled = data.get("enabled", True)
            priority = data.get("priority", 0)
            notification_threshold = data.get("notification_threshold", 1)

            if not site_key or not cron_expression:
                raise HTTPException(status_code=400, detail="site_key와 cron_expression이 필요합니다")

            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            success = context.scheduler_service.add_crawl_schedule(
                site_key,
                cron_expression,
                enabled,
                priority,
                notification_threshold,
            )

            if success:
                return {
                    "status": "success",
                    "message": f"{context.site_info[site_key]['name']} 스케줄이 업데이트되었습니다",
                    "site_key": site_key,
                }
            raise HTTPException(status_code=500, detail="스케줄 업데이트 실패")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 생성/수정 실패: {str(e)}")

    @router.delete("/api/schedules/{site_key}")
    async def delete_schedule(site_key: str):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            success = context.scheduler_service.remove_crawl_schedule(site_key)

            if success:
                return {
                    "status": "success",
                    "message": f"{context.site_info[site_key]['name']} 스케줄이 비활성화되었습니다",
                }
            raise HTTPException(status_code=500, detail="스케줄 삭제 실패")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 삭제 실패: {str(e)}")

    @router.post("/api/schedules/{site_key}/trigger")
    async def trigger_manual_crawl(site_key: str, request: Request):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            data = await request.json()
            delay_seconds = data.get("delay_seconds", 0)

            success = context.scheduler_service.trigger_manual_crawl(site_key, delay_seconds)

            if success:
                return {
                    "status": "success",
                    "message": f"{context.site_info[site_key]['name']} 수동 크롤링이 예약되었습니다",
                    "delay_seconds": delay_seconds,
                }
            raise HTTPException(status_code=500, detail="수동 크롤링 트리거 실패")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"수동 크롤링 트리거 실패: {str(e)}")

    return router
