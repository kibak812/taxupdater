"""
Tax Law Crawler Web Application - FastAPI entrypoint.

The default ``app`` object is still exported for ``uvicorn src.web.app:app``.
The actual dependency wiring lives in ``src.web.factory`` so tests can create
an app with fakes instead of touching the production database or crawlers.
"""

import os
import sys
from pathlib import Path

import uvicorn

# Windows cp949 인코딩 문제 해결: stdout/stderr를 UTF-8로 강제 설정
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.web.context import ConnectionManager, get_configured_ngrok_url
from src.web.factory import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
