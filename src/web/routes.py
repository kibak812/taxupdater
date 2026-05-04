"""FastAPI route registration for the TaxUpdater web app."""

from src.web.context import WebAppContext
from src.web.routers.crawl import create_crawl_router
from src.web.routers.data import create_data_router
from src.web.routers.notifications import create_notification_router
from src.web.routers.pages import create_page_router
from src.web.routers.realtime import create_websocket_router
from src.web.routers.schedules import create_schedule_router
from src.web.routers.settings import create_settings_router
from src.web.routers.system import (
    create_shutdown_handler,
    create_startup_handler,
    create_system_router,
)
from src.web.routers.tunnel import create_tunnel_router


def register_routes(app, context: WebAppContext) -> None:
    app.include_router(create_system_router(context))
    app.include_router(create_page_router(context))
    app.include_router(create_data_router(context))
    app.include_router(create_crawl_router(context))
    app.include_router(create_schedule_router(context))
    app.include_router(create_notification_router(context))
    app.include_router(create_settings_router(context))
    app.include_router(create_tunnel_router(context))
    app.include_router(create_websocket_router(context))
    app.add_event_handler("startup", create_startup_handler(context))
    app.add_event_handler("shutdown", create_shutdown_handler(context))
