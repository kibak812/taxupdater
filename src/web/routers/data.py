import json
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from src.web.context import WebAppContext
from src.web.helpers import build_dashboard_payload, build_site_data_payload


def create_data_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.get("/api/dashboard")
    async def get_dashboard_data():
        try:
            return build_dashboard_payload(context.site_info, context.repository)
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

    @router.get("/api/stats")
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

    @router.get("/api/sites/recent-counts")
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

    @router.get("/api/new-data")
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

    return router
