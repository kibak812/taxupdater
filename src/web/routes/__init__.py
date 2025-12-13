# Web routes
from .dashboard_routes import create_dashboard_router
from .crawl_routes import create_crawl_router
from .schedule_routes import create_schedule_router
from .notification_routes import create_notification_router
from .settings_routes import create_settings_router

__all__ = [
    'create_dashboard_router',
    'create_crawl_router',
    'create_schedule_router',
    'create_notification_router',
    'create_settings_router'
]
