import sqlite3
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.web.context import WebAppContext


def create_system_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()
    logger = context.logger

    @router.get("/health")
    async def health_check():
        """Health check endpoint for Railway/container orchestration."""
        try:
            with sqlite3.connect(context.repository.db_path) as conn:
                conn.execute("SELECT 1")

            return {
                "status": "healthy",
                "database": "connected",
                "scheduler": (
                    "running"
                    if (context.scheduler_service and context.scheduler_service.is_running())
                    else "stopped"
                ),
            }
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)},
            )

    @router.get("/api/system-status")
    async def get_system_status():
        try:
            scheduler_status = {
                "scheduler_running": (
                    context.scheduler_service.is_running() if context.scheduler_service else False
                ),
                "active_jobs": (
                    len(context.scheduler_service.scheduler.get_jobs())
                    if context.scheduler_service and context.scheduler_service.is_running()
                    else 0
                ),
                "service_available": context.scheduler_service is not None,
            }

            system_status = []
            try:
                with sqlite3.connect(context.repository.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='system_status'"
                    )
                    if cursor.fetchone():
                        cursor.execute(
                            """
                            SELECT site_key, component_type, status, last_check, last_success,
                                   last_error, error_message, consecutive_errors, health_score,
                                   uptime_seconds, response_time_ms
                            FROM system_status
                            ORDER BY site_key, component_type
                            """
                        )

                        columns = [desc[0] for desc in cursor.description]

                        for row in cursor.fetchall():
                            status_row = dict(zip(columns, row))
                            status_row["site_name"] = context.site_info.get(
                                status_row["site_key"],
                                {},
                            ).get("name", status_row["site_key"])
                            system_status.append(status_row)
                    else:
                        for site_key, site_info in context.site_info.items():
                            system_status.append(
                                {
                                    "site_key": site_key,
                                    "site_name": site_info["name"],
                                    "component_type": "crawler",
                                    "status": "unknown",
                                    "health_score": 50,
                                    "last_check": None,
                                    "error_message": "system_status 테이블 없음",
                                }
                            )
            except sqlite3.Error as db_error:
                logger.warning(f"시스템 상태 DB 조회 실패: {db_error}")

            return {
                "system_status": system_status,
                "scheduler_status": scheduler_status,
                "timestamp": datetime.now().isoformat(),
                "monitoring_available": context.scheduler_service is not None,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"시스템 상태 조회 실패: {str(e)}")

    @router.get("/api/job-history")
    async def get_job_history(site_key: str = None, limit: int = 50):
        try:
            history = context.scheduler_service.get_job_history(site_key, limit)

            for item in history:
                item["site_name"] = context.site_info.get(item["site_key"], {}).get(
                    "name",
                    item["site_key"],
                )

            return {
                "job_history": history,
                "total_count": len(history),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"작업 이력 조회 실패: {str(e)}")

    @router.delete("/api/job-history")
    async def clear_job_history():
        try:
            success = context.scheduler_service.clear_job_history()

            if success:
                return {
                    "status": "success",
                    "message": "크롤링 진행현황이 모두 삭제되었습니다",
                }
            raise HTTPException(status_code=500, detail="진행현황 삭제 실패")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"진행현황 삭제 실패: {str(e)}")

    @router.post("/api/scheduler/start")
    async def start_scheduler():
        try:
            if context.scheduler_service.is_running():
                return {
                    "status": "already_running",
                    "message": "스케줄러가 이미 실행 중입니다",
                }

            context.scheduler_service.start()

            await context.notification_service.send_system_notification(
                "스케줄러가 시작되었습니다",
                "normal",
                "system",
            )

            return {
                "status": "started",
                "message": "스케줄러가 시작되었습니다",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄러 시작 실패: {str(e)}")

    @router.post("/api/scheduler/stop")
    async def stop_scheduler():
        try:
            if not context.scheduler_service.is_running():
                return {
                    "status": "already_stopped",
                    "message": "스케줄러가 이미 중지되어 있습니다",
                }

            context.scheduler_service.stop()

            await context.notification_service.send_system_notification(
                "스케줄러가 중지되었습니다",
                "normal",
                "system",
            )

            return {
                "status": "stopped",
                "message": "스케줄러가 중지되었습니다",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄러 중지 실패: {str(e)}")

    return router


def create_startup_handler(context: WebAppContext):
    async def startup_event():
        context.logger.info("FastAPI 서버 시작")
        context.logger.info("웹 인터페이스: http://localhost:8001")

        try:
            context.scheduler_service.start()
            context.logger.info("자동 스케줄러 시작됨")

            await context.notification_service.send_system_notification(
                "모니터링 시스템이 시작되었습니다",
                "normal",
                "system",
            )
        except Exception as e:
            context.logger.error(f"스케줄러 시작 실패: {e}")

    return startup_event


def create_shutdown_handler(context: WebAppContext):
    async def shutdown_event():
        context.logger.info("FastAPI 서버 종료")

        try:
            if context.scheduler_service.is_running():
                context.scheduler_service.stop()
                context.logger.info("스케줄러 정상 종료됨")
        except Exception as e:
            context.logger.error(f"스케줄러 종료 실패: {e}")

    return shutdown_event
