from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from src.web.context import WebAppContext

ASSET_VERSION = "fe-20260702"


def _page_context(request: Request, active_nav: str, **extra) -> dict:
    return {
        "request": request,
        "asset_version": ASSET_VERSION,
        "active_nav": active_nav,
        **extra,
    }


def create_page_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    @router.get("/dashboard", response_class=HTMLResponse)
    async def main_dashboard(request: Request):
        return context.templates.TemplateResponse(
            "dashboard.html", _page_context(request, "dashboard")
        )

    @router.get("/legacy", response_class=HTMLResponse)
    async def legacy_dashboard(request: Request):
        return context.templates.TemplateResponse("monitoring.html", {"request": request})

    @router.get("/legacy/old", response_class=HTMLResponse)
    async def legacy_old_dashboard(request: Request):
        return context.templates.TemplateResponse("index.html", {"request": request})

    @router.get("/data/{site_key}", response_class=HTMLResponse)
    async def data_table_view(request: Request, site_key: str):
        if site_key not in context.site_info:
            raise HTTPException(status_code=404, detail="Site not found")

        site_info = context.site_info[site_key]
        return context.templates.TemplateResponse(
            "data_table.html",
            _page_context(
                request,
                "dashboard",
                site_key=site_key,
                site_name=site_info["name"],
                site_color=site_info["color"],
            ),
        )

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        return context.templates.TemplateResponse(
            "settings.html", _page_context(request, "settings")
        )

    @router.get("/sites/{site_key}", response_class=HTMLResponse)
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

    return router
