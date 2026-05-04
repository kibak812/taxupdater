"""FastAPI route registration for the TaxUpdater web app."""

import asyncio
import concurrent.futures
import json
import re
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from src.config.sites import get_choice_by_key
from src.web.context import WebAppContext, get_configured_ngrok_url
from src.web.helpers import build_dashboard_payload, build_site_data_payload


def register_routes(app, context: WebAppContext) -> None:
    page_router = APIRouter()
    data_router = APIRouter()
    crawl_router = APIRouter()
    schedule_router = APIRouter()
    notification_router = APIRouter()
    system_router = APIRouter()
    settings_router = APIRouter()
    tunnel_router = APIRouter()
    websocket_router = APIRouter()

    logger = context.logger

    @system_router.get("/health")
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

    @page_router.get("/", response_class=HTMLResponse)
    async def main_dashboard(request: Request):
        return context.templates.TemplateResponse("dashboard.html", {"request": request})

    @page_router.get("/dashboard", response_class=HTMLResponse)
    async def expert_dashboard(request: Request):
        return context.templates.TemplateResponse("dashboard.html", {"request": request})

    @page_router.get("/legacy", response_class=HTMLResponse)
    async def legacy_dashboard(request: Request):
        return context.templates.TemplateResponse("monitoring.html", {"request": request})

    @page_router.get("/legacy/old", response_class=HTMLResponse)
    async def legacy_old_dashboard(request: Request):
        return context.templates.TemplateResponse("index.html", {"request": request})

    @page_router.get("/data/{site_key}", response_class=HTMLResponse)
    async def data_table_view(request: Request, site_key: str):
        if site_key not in context.site_info:
            raise HTTPException(status_code=404, detail="Site not found")

        site_info = context.site_info[site_key]
        return context.templates.TemplateResponse(
            "data_table.html",
            {
                "request": request,
                "site_key": site_key,
                "site_name": site_info["name"],
                "site_color": site_info["color"],
            },
        )

    @page_router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        return context.templates.TemplateResponse("settings.html", {"request": request})

    @page_router.get("/sites/{site_key}", response_class=HTMLResponse)
    async def site_detail(request: Request, site_key: str):
        if site_key not in context.site_info:
            raise HTTPException(status_code=404, detail="Site not found")

        site_info = context.site_info[site_key]
        return context.templates.TemplateResponse(
            "site.html",
            {
                "request": request,
                "site_key": site_key,
                "site_name": site_info["name"],
            },
        )

    @data_router.get("/api/dashboard")
    async def get_dashboard_data():
        try:
            return build_dashboard_payload(context.site_info, context.repository)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dashboard data error: {str(e)}")

    @data_router.get("/api/sites/{site_key}/data")
    async def get_site_data(
        site_key: str,
        page: int = 1,
        limit: int = 50,
        search: str = "",
        filter: str = None,
        days: int = None,
        start: str = None,
        end: str = None,
    ):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            if filter == "recent" and days:
                data = context.repository.load_filtered_data(site_key, recent_days=days)
            elif filter == "range" and start and end:
                data = context.repository.load_filtered_data(site_key, start_date=start, end_date=end)
            else:
                data = context.repository.load_existing_data(site_key, include_metadata=True)

            return build_site_data_payload(
                site_key,
                context.site_info,
                data,
                page=page,
                limit=limit,
                search=search,
                filter_type=filter,
                days=days,
                start=start,
                end=end,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Site data error: {str(e)}")

    @crawl_router.post("/api/crawl/all")
    async def start_all_crawling():
        try:
            logger.info("전체 크롤링 API 함수 진입")
            logger.info(f"사용 가능한 크롤러: {list(context.crawlers.keys())}")
            logger.info(f"SITE_INFO 키: {list(context.site_info.keys())}")

            async def run_all_crawling():
                try:
                    await context.manager.broadcast(
                        {
                            "type": "crawl_start",
                            "choice": "all",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    def run_all_sync():
                        try:
                            logger.info("전체 크롤링 시작 (동기)")
                            result = context.scheduler_service._execute_all_sites_crawl()
                            logger.info("전체 크롤링 완료")
                            return {"status": "success", "result": result}
                        except Exception as e:
                            logger.error(f"전체 크롤링 오류: {e}")
                            return {"status": "error", "error": str(e)}

                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = await loop.run_in_executor(executor, run_all_sync)

                    if result["status"] == "success":
                        await context.manager.broadcast(
                            {
                                "type": "crawl_complete",
                                "choice": "all",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    else:
                        await context.manager.broadcast(
                            {
                                "type": "crawl_error",
                                "error": result.get("error", "알 수 없는 오류"),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                except Exception as e:
                    logger.error(f"전체 크롤링 태스크 오류: {e}")
                    await context.manager.broadcast(
                        {
                            "type": "crawl_error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            asyncio.create_task(run_all_crawling())

            return {
                "status": "started",
                "message": "전체 사이트 크롤링을 시작했습니다.",
            }
        except Exception as e:
            logger.error(f"전체 크롤링 시작 에러: {str(e)}")
            raise HTTPException(status_code=500, detail=f"All crawling start error: {str(e)}")

    @crawl_router.post("/api/crawl/{site_key}")
    async def start_crawling(site_key: str):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            try:
                choice = get_choice_by_key(site_key)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid site_key: {site_key}")

            if context.scheduler_service:
                success = context.scheduler_service.trigger_manual_crawl(site_key)
                if not success:
                    raise HTTPException(status_code=500, detail="크롤링 실행 실패")
            else:
                asyncio.create_task(run_crawling_task(choice, context))

            return {
                "status": "started",
                "site_key": site_key,
                "site_name": context.site_info[site_key]["name"],
                "message": f"{context.site_info[site_key]['name']} 크롤링을 시작했습니다.",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Crawling start error: {str(e)}")

    @data_router.get("/api/stats")
    async def get_statistics():
        try:
            total_records = 0
            site_stats = {}

            for site_key, site_info in context.site_info.items():
                stats = context.repository.get_statistics(site_key)
                site_count = stats.get("total_count", 0)
                total_records += site_count

                site_stats[site_key] = {
                    "name": site_info["name"],
                    "count": site_count,
                    "last_updated": stats.get("last_updated"),
                }

            return {
                "total_records": total_records,
                "site_stats": site_stats,
                "database_info": context.repository.get_database_info(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Statistics error: {str(e)}")

    @schedule_router.get("/api/schedules")
    async def get_schedules():
        try:
            if not context.scheduler_service:
                raise HTTPException(status_code=503, detail="스케줄러 서비스를 사용할 수 없습니다")

            return context.scheduler_service.get_schedule_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"스케줄 조회 실패: {str(e)}")

    @schedule_router.get("/api/schedules/{site_key}")
    async def get_site_schedule(site_key: str):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            return context.scheduler_service.get_schedule_status(site_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"사이트 스케줄 조회 실패: {str(e)}")

    @schedule_router.post("/api/schedules")
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

    @schedule_router.delete("/api/schedules/{site_key}")
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

    @schedule_router.post("/api/schedules/{site_key}/trigger")
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

    @notification_router.get("/api/notifications")
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

    @notification_router.post("/api/notifications/{notification_id}/read")
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

    @notification_router.get("/api/notifications/stats")
    async def get_notification_stats(site_key: str = None):
        try:
            return await context.notification_service.get_notification_stats(site_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알림 통계 조회 실패: {str(e)}")

    @data_router.get("/api/sites/recent-counts")
    async def get_recent_data_counts(hours: int = 24):
        try:
            counts = context.repository.get_recent_data_counts(hours)

            result = {}
            for site_key, count in counts.items():
                result[site_key] = {
                    "count": count,
                    "site_name": context.site_info.get(site_key, {}).get("name", site_key),
                }

            return {
                "recent_counts": result,
                "hours": hours,
                "total_new_items": sum(counts.values()),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"최근 데이터 개수 조회 실패: {str(e)}")

    @data_router.get("/api/new-data")
    async def get_new_data(site_key: str = None, hours: int = 24, limit: int = 100):
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            with sqlite3.connect(context.repository.db_path) as conn:
                cursor = conn.cursor()

                where_conditions = ["discovered_at >= ?"]
                params = [cutoff_time.isoformat()]

                if site_key:
                    where_conditions.append("site_key = ?")
                    params.append(site_key)

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT log_id, site_key, data_id, data_title, data_summary,
                           data_category, data_date, discovered_at, is_important,
                           notification_sent, tags, metadata
                    FROM new_data_log
                    WHERE {where_clause}
                    ORDER BY discovered_at DESC
                    LIMIT ?
                """

                params.append(limit)
                cursor.execute(query, params)

                columns = [desc[0] for desc in cursor.description]
                new_data = []

                for row in cursor.fetchall():
                    data_row = dict(zip(columns, row))

                    if data_row["tags"]:
                        data_row["tags"] = json.loads(data_row["tags"])
                    if data_row["metadata"]:
                        data_row["metadata"] = json.loads(data_row["metadata"])

                    data_row["site_name"] = context.site_info.get(
                        data_row["site_key"],
                        {},
                    ).get("name", data_row["site_key"])

                    new_data.append(data_row)

            return {
                "new_data": new_data,
                "total_count": len(new_data),
                "hours": hours,
                "cutoff_time": cutoff_time.isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"새로운 데이터 조회 실패: {str(e)}")

    @system_router.get("/api/system-status")
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

    @system_router.get("/api/job-history")
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

    @system_router.delete("/api/job-history")
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

    @system_router.post("/api/scheduler/start")
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

    @system_router.post("/api/scheduler/stop")
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

    @settings_router.get("/api/email-settings")
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

    @settings_router.post("/api/email-settings")
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

    @settings_router.post("/api/email-settings/test")
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

    @tunnel_router.get("/api/tunnel-status")
    async def get_tunnel_status():
        try:
            import requests
            import subprocess

            configured_ngrok_url = get_configured_ngrok_url()
            tunnel_status = {
                "ngrok": {
                    "status": "unknown",
                    "url": None,
                    "configured_url": configured_ngrok_url or None,
                    "is_static": False,
                }
            }

            try:
                result = subprocess.run(
                    ["pgrep", "-x", "ngrok"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    tunnel_status["ngrok"]["status"] = "active"
                    try:
                        response = requests.get("http://localhost:4040/api/tunnels", timeout=3)
                        if response.status_code == 200:
                            tunnels = response.json().get("tunnels", [])
                            if tunnels:
                                public_url = tunnels[0].get("public_url")
                                tunnel_status["ngrok"]["url"] = public_url
                                tunnel_status["ngrok"]["is_static"] = bool(
                                    configured_ngrok_url and public_url == configured_ngrok_url
                                )
                                if configured_ngrok_url and public_url != configured_ngrok_url:
                                    tunnel_status["ngrok"]["status"] = "active_dynamic"
                    except Exception:
                        pass
                else:
                    tunnel_status["ngrok"]["status"] = (
                        "static_unconfigured" if not configured_ngrok_url else "inactive"
                    )
            except Exception as e:
                tunnel_status["ngrok"]["status"] = f"error: {str(e)}"

            return tunnel_status
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 상태 확인 실패: {str(e)}")

    @tunnel_router.post("/api/tunnel/start/{tunnel_type}")
    async def start_tunnel(tunnel_type: str):
        try:
            import shutil
            import subprocess

            if tunnel_type == "ngrok":
                if shutil.which("systemctl"):
                    result = subprocess.run(
                        ["systemctl", "--user", "start", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        return {"message": "ngrok이 시작되었습니다", "success": True}
                    raise HTTPException(status_code=500, detail=f"ngrok 시작 실패: {result.stderr}")

                if not shutil.which("ngrok"):
                    raise HTTPException(status_code=500, detail="ngrok이 설치되어 있지 않습니다")

                log_path = context.project_root / "logs" / "ngrok.log"
                log_path.parent.mkdir(exist_ok=True)
                log_file = open(log_path, "a")
                command = ["ngrok", "http", "8001"]
                configured_ngrok_url = get_configured_ngrok_url()
                if configured_ngrok_url:
                    command.extend(["--url", configured_ngrok_url])
                subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=str(context.project_root),
                    start_new_session=True,
                )
                return {"message": "ngrok 시작 명령을 실행했습니다", "success": True}

            raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 시작 실패: {str(e)}")

    @tunnel_router.post("/api/tunnel/stop/{tunnel_type}")
    async def stop_tunnel(tunnel_type: str):
        try:
            import shutil
            import subprocess

            if tunnel_type == "ngrok":
                if shutil.which("systemctl"):
                    result = subprocess.run(
                        ["systemctl", "--user", "stop", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                else:
                    result = subprocess.run(
                        ["pkill", "-x", "ngrok"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                if result.returncode in (0, 1):
                    return {"message": "ngrok이 중지되었습니다", "success": True}
                raise HTTPException(status_code=500, detail=f"ngrok 중지 실패: {result.stderr}")

            raise HTTPException(status_code=400, detail="지원하지 않는 터널 타입입니다")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"터널 중지 실패: {str(e)}")

    @websocket_router.websocket("/ws/crawl")
    async def websocket_endpoint(websocket: WebSocket):
        await context.manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            context.manager.disconnect(websocket)

    async def startup_event():
        logger.info("FastAPI 서버 시작")
        logger.info("웹 인터페이스: http://localhost:8001")

        try:
            context.scheduler_service.start()
            logger.info("자동 스케줄러 시작됨")

            await context.notification_service.send_system_notification(
                "모니터링 시스템이 시작되었습니다",
                "normal",
                "system",
            )
        except Exception as e:
            logger.error(f"스케줄러 시작 실패: {e}")

    async def shutdown_event():
        logger.info("FastAPI 서버 종료")

        try:
            if context.scheduler_service.is_running():
                context.scheduler_service.stop()
                logger.info("스케줄러 정상 종료됨")
        except Exception as e:
            logger.error(f"스케줄러 종료 실패: {e}")

    app.include_router(system_router)
    app.include_router(page_router)
    app.include_router(data_router)
    app.include_router(crawl_router)
    app.include_router(schedule_router)
    app.include_router(notification_router)
    app.include_router(settings_router)
    app.include_router(tunnel_router)
    app.include_router(websocket_router)
    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)


async def run_crawling_task(choice: str, context: WebAppContext):
    """Run a crawl task in a thread while broadcasting progress over WebSocket."""
    logger = context.logger

    try:
        await context.manager.broadcast(
            {
                "type": "crawl_start",
                "choice": choice,
                "timestamp": datetime.now().isoformat(),
            }
        )

        class WebSocketProgress:
            def __init__(self, loop, manager, choice):
                self.value = 0
                self.loop = loop
                self.manager = manager
                self.choice = choice

            def update(self):
                try:
                    message = {
                        "type": "crawl_progress",
                        "choice": self.choice,
                        "progress": self.value,
                        "timestamp": datetime.now().isoformat(),
                    }
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message),
                        self.loop,
                    )
                except Exception as e:
                    logger.error(f"진행률 WebSocket 전송 오류: {e}")

        class WebSocketStatus:
            def __init__(self, loop, manager, choice):
                self.text = ""
                self.loop = loop
                self.manager = manager
                self.choice = choice

            def config(self, text):
                self.text = text
                try:
                    message = {
                        "type": "crawl_status",
                        "choice": self.choice,
                        "status": text,
                        "timestamp": datetime.now().isoformat(),
                    }
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message),
                        self.loop,
                    )
                except Exception as e:
                    logger.error(f"상태 WebSocket 전송 오류: {e}")

            def update(self):
                if self.text:
                    self.config(self.text)

        def run_sync_crawling():
            try:
                progress = WebSocketProgress(loop, context.manager, choice)
                status = WebSocketStatus(loop, context.manager, choice)

                logger.info(f"크롤링 실행 시작: choice={choice}")
                context.crawling_service.execute_crawling(choice, progress, status, is_periodic=False)
                logger.info(f"크롤링 실행 완료: choice={choice}")
                return {"status": "success", "message": "크롤링 완료"}
            except Exception as e:
                logger.error(f"크롤링 실행 오류 (choice={choice}): {e}")
                logger.error(f"오류 타입: {type(e).__name__}")
                import traceback

                logger.error(f"스택 트레이스: {traceback.format_exc()}")
                return {"status": "error", "error": str(e)}

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_sync_crawling)

        if result["status"] == "success":
            await context.manager.broadcast(
                {
                    "type": "crawl_complete",
                    "choice": choice,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            await context.manager.broadcast(
                {
                    "type": "crawl_error",
                    "error": result.get("error", "알 수 없는 오류"),
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        await context.manager.broadcast(
            {
                "type": "crawl_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
