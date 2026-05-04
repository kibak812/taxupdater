"""Pure-ish helpers for building web API response payloads."""

from datetime import datetime
from typing import Any, Dict, Optional


def normalize_iso_datetime(value: Any) -> Any:
    """Return an ISO datetime string when ``value`` can be parsed."""
    if not value:
        return value
    try:
        return datetime.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return value


def build_dashboard_payload(site_info: Dict[str, Dict[str, str]], repository, now=None) -> Dict[str, Any]:
    dashboard_data = []

    for site_key, info in site_info.items():
        stats = repository.get_statistics(site_key)
        total_count = stats.get("total_count", 0)

        dashboard_data.append(
            {
                "site_key": site_key,
                "site_name": info["name"],
                "color": info["color"],
                "total_count": total_count,
                "last_updated": normalize_iso_datetime(stats.get("last_updated")),
                "status": "success" if total_count > 0 else "empty",
            }
        )

    refresh_time = now or datetime.now()
    return {
        "sites": dashboard_data,
        "last_refresh": refresh_time.isoformat(),
    }


def filter_text_columns(data, search: str):
    if not search or data.empty:
        return data

    text_columns = data.select_dtypes(include=["object"]).columns
    if len(text_columns) == 0:
        return data.iloc[0:0]

    mask = data[text_columns].astype(str).apply(
        lambda column: column.str.contains(search, case=False, na=False)
    ).any(axis=1)
    return data[mask]


def build_site_data_payload(
    site_key: str,
    site_info: Dict[str, Dict[str, str]],
    data,
    page: int = 1,
    limit: int = 50,
    search: str = "",
    filter_type: Optional[str] = None,
    days: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    data = filter_text_columns(data, search)

    total_count = len(data)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_data = data.iloc[start_idx:end_idx]

    filter_info = None
    if filter_type:
        filter_info = {
            "type": filter_type,
            "days": days,
            "start": start,
            "end": end,
        }

    return {
        "site_key": site_key,
        "site_name": site_info[site_key]["name"],
        "data": page_data.to_dict("records"),
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "has_next": end_idx < total_count,
            "has_prev": page > 1,
        },
        "search": search,
        "filter": filter_info,
    }
