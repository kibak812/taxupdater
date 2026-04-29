"""
대시보드 라우터

엔드포인트:
- GET / : 메인 대시보드
- GET /dashboard : 전문가용 대시보드
- GET /legacy : 레거시 모니터링
- GET /data/{site_key} : 데이터 테이블 뷰
- GET /api/dashboard : 대시보드 데이터
- GET /api/stats : 통계
- GET /api/sites/recent-counts : 최근 데이터 카운트
- GET /api/sites/{site_key}/data : 사이트 데이터 조회
- GET /api/new-data : 새로운 데이터 조회
- GET /api/system-status : 시스템 상태
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
from datetime import datetime


def create_dashboard_router(
    templates: Jinja2Templates,
    repository: Any,
    site_info: Dict[str, Dict],
    notification_service: Optional[Any] = None,
    scheduler_service: Optional[Any] = None
) -> APIRouter:
    """
    대시보드 라우터 생성

    Args:
        templates: Jinja2 템플릿 엔진
        repository: 데이터 저장소
        site_info: 사이트 정보 매핑
        notification_service: 알림 서비스 (선택)
        scheduler_service: 스케줄러 서비스 (선택)
    """
    router = APIRouter()

    # ========== 페이지 라우트 ==========

    @router.get("/", response_class=HTMLResponse)
    async def main_dashboard(request: Request):
        """메인 페이지 - 새로운 전문가용 대시보드"""
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @router.get("/dashboard", response_class=HTMLResponse)
    async def expert_dashboard(request: Request):
        """전문가용 대시보드 페이지"""
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @router.get("/legacy", response_class=HTMLResponse)
    async def legacy_dashboard(request: Request):
        """레거시 모니터링 시스템"""
        return templates.TemplateResponse("monitoring.html", {"request": request})

    @router.get("/legacy/old", response_class=HTMLResponse)
    async def legacy_old_dashboard(request: Request):
        """레거시 대시보드 페이지 (구 버전)"""
        return templates.TemplateResponse("index.html", {"request": request})

    @router.get("/data/{site_key}", response_class=HTMLResponse)
    async def data_table_view(request: Request, site_key: str):
        """전문가용 데이터 목록 뷰"""
        if site_key not in site_info:
            raise HTTPException(status_code=404, detail="Site not found")

        info = site_info[site_key]
        return templates.TemplateResponse("data_table.html", {
            "request": request,
            "site_key": site_key,
            "site_name": info["name"],
            "site_color": info["color"]
        })

    @router.get("/sites/{site_key}", response_class=HTMLResponse)
    async def site_detail(request: Request, site_key: str):
        """사이트별 상세 페이지 (레거시)"""
        if site_key not in site_info:
            raise HTTPException(status_code=404, detail="Site not found")

        info = site_info[site_key]
        return templates.TemplateResponse("site.html", {
            "request": request,
            "site_key": site_key,
            "site_name": info["name"]
        })

    # ========== API 라우트 ==========

    @router.get("/api/dashboard")
    async def get_dashboard_data():
        """대시보드 데이터 조회"""
        try:
            dashboard_data = []

            for key, info in site_info.items():
                stats = repository.get_statistics(key)

                last_updated = stats.get("last_updated")
                if last_updated:
                    try:
                        dt = datetime.fromisoformat(last_updated)
                        last_updated = dt.isoformat()
                    except (ValueError, TypeError):
                        pass

                dashboard_data.append({
                    "site_key": key,
                    "site_name": info["name"],
                    "color": info["color"],
                    "total_count": stats.get("total_count", 0),
                    "last_updated": last_updated,
                    "status": "success" if stats.get("total_count", 0) > 0 else "empty"
                })

            return {
                "sites": dashboard_data,
                "last_refresh": datetime.now().isoformat()
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dashboard data error: {str(e)}")

    @router.get("/api/sites/{site_key}/data")
    async def get_site_data(
        site_key: str,
        page: int = 1,
        limit: int = 50,
        search: str = "",
        filter: str = None,
        days: int = None,
        start: str = None,
        end: str = None
    ):
        """사이트별 데이터 조회 (페이지네이션 + 시간 필터링)"""
        try:
            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            if filter == "recent" and days:
                data = repository.load_filtered_data(site_key, recent_days=days)
            elif filter == "range" and start and end:
                data = repository.load_filtered_data(site_key, start_date=start, end_date=end)
            else:
                data = repository.load_existing_data(site_key, include_metadata=True)

            if search:
                text_columns = data.select_dtypes(include=['object']).columns
                mask = data[text_columns].astype(str).apply(
                    lambda x: x.str.contains(search, case=False, na=False)
                ).any(axis=1)
                data = data[mask]

            total_count = len(data)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_data = data.iloc[start_idx:end_idx]

            records = page_data.to_dict('records')

            filter_info = None
            if filter:
                filter_info = {
                    "type": filter,
                    "days": days,
                    "start": start,
                    "end": end
                }

            return {
                "site_key": site_key,
                "site_name": site_info[site_key]["name"],
                "data": records,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total_count + limit - 1) // limit
                },
                "filter": filter_info
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data fetch error: {str(e)}")

    @router.get("/api/stats")
    async def get_stats():
        """전체 통계 조회"""
        try:
            stats_data = {}

            for key, info in site_info.items():
                stats = repository.get_statistics(key)
                stats_data[key] = {
                    "name": info["name"],
                    "total_count": stats.get("total_count", 0),
                    "last_updated": stats.get("last_updated")
                }

            return {
                "stats": stats_data,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/sites/recent-counts")
    async def get_recent_counts(days: int = 7):
        """최근 N일간 사이트별 데이터 카운트"""
        try:
            recent_counts = {}

            for key, info in site_info.items():
                try:
                    count = repository.get_recent_count(key, days=days)
                    recent_counts[key] = {
                        "name": info["name"],
                        "color": info["color"],
                        "recent_count": count,
                        "days": days
                    }
                except Exception:
                    recent_counts[key] = {
                        "name": info["name"],
                        "color": info["color"],
                        "recent_count": 0,
                        "days": days
                    }

            return {
                "recent_counts": recent_counts,
                "days": days,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/new-data")
    async def get_new_data(
        site_key: str = None,
        days: int = 7,
        page: int = 1,
        limit: int = 50
    ):
        """새로운 데이터 조회 (최근 N일)"""
        try:
            all_new_data = []
            target_sites = [site_key] if site_key else list(site_info.keys())

            for key in target_sites:
                if key not in site_info:
                    continue

                try:
                    data = repository.load_filtered_data(key, recent_days=days)

                    if not data.empty:
                        records = data.to_dict('records')
                        for record in records:
                            record['site_key'] = key
                            record['site_name'] = site_info[key]["name"]
                            record['site_color'] = site_info[key]["color"]
                        all_new_data.extend(records)
                except Exception:
                    continue

            all_new_data.sort(
                key=lambda x: x.get('created_at', x.get('결정일', x.get('생산일자', ''))),
                reverse=True
            )

            total_count = len(all_new_data)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_data = all_new_data[start_idx:end_idx]

            return {
                "data": page_data,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total_count + limit - 1) // limit
                },
                "filter": {
                    "site_key": site_key,
                    "days": days
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/system-status")
    async def get_system_status():
        """시스템 상태 조회"""
        try:
            status = {
                "scheduler": {
                    "running": False,
                    "job_count": 0,
                    "next_runs": {}
                },
                "crawlers": {},
                "database": {
                    "connected": True,
                    "path": getattr(repository, 'db_path', 'unknown')
                },
                "notifications": {
                    "enabled": notification_service is not None,
                    "unread_count": 0
                }
            }

            if scheduler_service:
                try:
                    status["scheduler"]["running"] = scheduler_service.is_running()
                    jobs = scheduler_service.get_all_jobs()
                    status["scheduler"]["job_count"] = len(jobs)

                    for job in jobs:
                        site_key = job.get('site_key')
                        if site_key:
                            status["scheduler"]["next_runs"][site_key] = job.get('next_run_time')
                except Exception:
                    pass

            for key, info in site_info.items():
                stats = repository.get_statistics(key)
                status["crawlers"][key] = {
                    "name": info["name"],
                    "color": info["color"],
                    "total_count": stats.get("total_count", 0),
                    "last_updated": stats.get("last_updated"),
                    "status": "active"
                }

            if notification_service:
                try:
                    unread = notification_service.get_unread_count()
                    status["notifications"]["unread_count"] = unread
                except Exception:
                    pass

            return {
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
