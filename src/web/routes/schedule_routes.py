"""
스케줄 라우터

엔드포인트:
- GET /api/schedules : 스케줄 목록 조회
- GET /api/schedules/{site_key} : 특정 사이트 스케줄 조회
- POST /api/schedules : 스케줄 생성/수정
- DELETE /api/schedules/{site_key} : 스케줄 삭제
- POST /api/schedules/{site_key}/trigger : 수동 크롤링 트리거
- POST /api/scheduler/start : 스케줄러 시작
- POST /api/scheduler/stop : 스케줄러 중지
- GET /api/job-history : 작업 이력 조회
- DELETE /api/job-history : 작업 이력 삭제
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, Optional


def create_schedule_router(
    site_info: Dict[str, Dict],
    scheduler_service: Optional[Any] = None,
    notification_service: Optional[Any] = None
) -> APIRouter:
    """
    스케줄 라우터 생성

    Args:
        site_info: 사이트 정보 매핑
        scheduler_service: 스케줄러 서비스
        notification_service: 알림 서비스 (선택)
    """
    router = APIRouter()

    def check_scheduler():
        if not scheduler_service:
            raise HTTPException(status_code=503, detail="스케줄러 서비스를 사용할 수 없습니다")

    @router.get("/api/schedules")
    async def get_schedules():
        """크롤링 스케줄 목록 조회"""
        try:
            check_scheduler()
            status = scheduler_service.get_schedule_status()
            return status
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 조회 실패: {str(e)}")

    @router.get("/api/schedules/{site_key}")
    async def get_site_schedule(site_key: str):
        """특정 사이트 스케줄 상세 조회"""
        try:
            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            check_scheduler()
            status = scheduler_service.get_schedule_status(site_key)
            return status
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"사이트 스케줄 조회 실패: {str(e)}")

    @router.post("/api/schedules")
    async def create_or_update_schedule(request: Request):
        """크롤링 스케줄 생성/수정"""
        try:
            check_scheduler()

            data = await request.json()
            site_key = data.get("site_key")
            cron_expression = data.get("cron_expression")
            enabled = data.get("enabled", True)
            priority = data.get("priority", 0)
            notification_threshold = data.get("notification_threshold", 1)

            if not site_key or not cron_expression:
                raise HTTPException(status_code=400, detail="site_key와 cron_expression이 필요합니다")

            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            success = scheduler_service.add_crawl_schedule(
                site_key, cron_expression, enabled, priority, notification_threshold
            )

            if success:
                return {
                    "status": "success",
                    "message": f"{site_info[site_key]['name']} 스케줄이 업데이트되었습니다",
                    "site_key": site_key
                }
            else:
                raise HTTPException(status_code=500, detail="스케줄 업데이트 실패")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 생성/수정 실패: {str(e)}")

    @router.delete("/api/schedules/{site_key}")
    async def delete_schedule(site_key: str):
        """크롤링 스케줄 삭제(비활성화)"""
        try:
            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            check_scheduler()
            success = scheduler_service.remove_crawl_schedule(site_key)

            if success:
                return {
                    "status": "success",
                    "message": f"{site_info[site_key]['name']} 스케줄이 비활성화되었습니다"
                }
            else:
                raise HTTPException(status_code=500, detail="스케줄 삭제 실패")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 삭제 실패: {str(e)}")

    @router.post("/api/schedules/{site_key}/trigger")
    async def trigger_manual_crawl(site_key: str, request: Request):
        """수동 크롤링 트리거"""
        try:
            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            check_scheduler()

            data = await request.json()
            delay_seconds = data.get("delay_seconds", 0)

            success = scheduler_service.trigger_manual_crawl(site_key, delay_seconds)

            if success:
                return {
                    "status": "success",
                    "message": f"{site_info[site_key]['name']} 수동 크롤링이 예약되었습니다",
                    "delay_seconds": delay_seconds
                }
            else:
                raise HTTPException(status_code=500, detail="수동 크롤링 트리거 실패")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"수동 크롤링 트리거 실패: {str(e)}")

    @router.post("/api/scheduler/start")
    async def start_scheduler():
        """스케줄러 시작"""
        try:
            check_scheduler()

            if scheduler_service.is_running():
                return {
                    "status": "already_running",
                    "message": "스케줄러가 이미 실행 중입니다"
                }

            scheduler_service.start()

            if notification_service:
                try:
                    await notification_service.send_system_notification(
                        "스케줄러가 시작되었습니다", "normal", "system"
                    )
                except Exception:
                    pass

            return {
                "status": "started",
                "message": "스케줄러가 시작되었습니다"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄러 시작 실패: {str(e)}")

    @router.post("/api/scheduler/stop")
    async def stop_scheduler():
        """스케줄러 중지"""
        try:
            check_scheduler()

            if not scheduler_service.is_running():
                return {
                    "status": "already_stopped",
                    "message": "스케줄러가 이미 중지되어 있습니다"
                }

            scheduler_service.stop()

            if notification_service:
                try:
                    await notification_service.send_system_notification(
                        "스케줄러가 중지되었습니다", "normal", "system"
                    )
                except Exception:
                    pass

            return {
                "status": "stopped",
                "message": "스케줄러가 중지되었습니다"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄러 중지 실패: {str(e)}")

    @router.get("/api/job-history")
    async def get_job_history(site_key: str = None, limit: int = 50):
        """작업 이력 조회"""
        try:
            check_scheduler()
            history = scheduler_service.get_job_history(site_key, limit)

            for item in history:
                item['site_name'] = site_info.get(item['site_key'], {}).get('name', item['site_key'])

            return {
                "job_history": history,
                "total_count": len(history)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"작업 이력 조회 실패: {str(e)}")

    @router.delete("/api/job-history")
    async def clear_job_history():
        """크롤링 진행현황 모두 삭제"""
        try:
            check_scheduler()
            success = scheduler_service.clear_job_history()

            if success:
                return {
                    "status": "success",
                    "message": "크롤링 진행현황이 모두 삭제되었습니다"
                }
            else:
                raise HTTPException(status_code=500, detail="진행현황 삭제 실패")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"진행현황 삭제 실패: {str(e)}")

    return router
