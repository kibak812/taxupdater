import json
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from src.config.settings import KEY_COLUMNS
from src.web.context import WebAppContext
from src.web.helpers import build_dashboard_payload, build_site_data_payload


LINK_COLUMNS = ("링크", "원문링크", "쟁점PDF", "보도자료링크")
DETAIL_COLUMNS = ("세목", "청구분야", "유형", "결론", "조세관련")


def _first_non_empty_link(values) -> str:
    for value in values:
        if value is None:
            continue
        link = str(value).strip()
        if link and link != "#":
            return link
    return ""


def _first_non_empty_value(values) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text != "-":
            return text
    return ""


def _build_item_details(values) -> dict:
    return {
        "external_link": _first_non_empty_link(values.get(column) for column in LINK_COLUMNS),
        "data_tax_category": _first_non_empty_value(
            values.get(column) for column in ("세목", "청구분야")
        ),
        "data_decision_type": _first_non_empty_value([values.get("유형")]),
        "data_conclusion": _first_non_empty_value([values.get("결론")]),
        "data_tax_status": _first_non_empty_value([values.get("조세관련")]),
    }


def _extract_details_from_metadata(metadata) -> dict:
    if not isinstance(metadata, dict):
        return {}

    original_data = metadata.get("original_data")
    if isinstance(original_data, dict):
        return _build_item_details(original_data)

    return {}


def _lookup_item_details(
    conn: sqlite3.Connection,
    site_key: str,
    data_id: str,
    context: WebAppContext,
    columns_cache: dict = None,
) -> dict:
    if not site_key or not data_id or site_key not in context.site_info:
        return {}

    table_name = context.repository._table_name(site_key)
    key_column = KEY_COLUMNS.get(site_key)
    if not key_column:
        return {}

    cursor = conn.cursor()
    if columns_cache is not None and table_name in columns_cache:
        existing_columns = columns_cache[table_name]
    else:
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if columns_cache is not None:
            columns_cache[table_name] = existing_columns
    if key_column not in existing_columns:
        return {}

    lookup_columns = [
        column
        for column in [*LINK_COLUMNS, *DETAIL_COLUMNS]
        if column in existing_columns
    ]
    if not lookup_columns:
        return {}

    select_columns = ", ".join(f"[{column}]" for column in lookup_columns)
    cursor.execute(
        f"SELECT {select_columns} FROM [{table_name}] WHERE [{key_column}] = ? LIMIT 1",
        (data_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {}

    return _build_item_details(dict(zip(lookup_columns, row)))


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
                table_columns_cache = {}

                for row in cursor.fetchall():
                    data_row = dict(zip(columns, row))

                    if data_row["tags"]:
                        data_row["tags"] = json.loads(data_row["tags"])
                    if data_row["metadata"]:
                        data_row["metadata"] = json.loads(data_row["metadata"])

                    item_details = _extract_details_from_metadata(data_row.get("metadata"))
                    lookup_details = _lookup_item_details(
                        conn,
                        data_row["site_key"],
                        data_row["data_id"],
                        context,
                        table_columns_cache,
                    )

                    for key, value in lookup_details.items():
                        if value and not item_details.get(key):
                            item_details[key] = value

                    data_row.update(
                        {
                            "external_link": item_details.get("external_link", ""),
                            "data_tax_category": item_details.get("data_tax_category", ""),
                            "data_decision_type": item_details.get("data_decision_type", ""),
                            "data_conclusion": item_details.get("data_conclusion", ""),
                            "data_tax_status": item_details.get("data_tax_status", ""),
                        }
                    )

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
