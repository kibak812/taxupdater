"""FastAPI app factory for TaxUpdater."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.web.context import WebAppContext, create_default_context
from src.web.routes import register_routes


def create_app(context: WebAppContext = None) -> FastAPI:
    context = context or create_default_context()

    app = FastAPI(
        title="Tax Law Crawler Web Interface",
        description="세금 법령 크롤링 시스템 웹 인터페이스 - 누락없는 데이터 수집과 새로운 데이터 식별",
        version="1.0.0",
    )
    app.state.context = context

    static_path = context.project_root / "src" / "web" / "static"
    templates_path = context.project_root / "src" / "web" / "templates"

    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    context.templates = Jinja2Templates(directory=str(templates_path))

    register_routes(app, context)
    return app
