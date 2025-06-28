"""
Tax Law Crawler Web Application - FastAPI 기반 웹 서버

기존 SQLite 기반 크롤링 시스템을 웹 인터페이스로 제공
핵심 목적: 누락없는 데이터 수집과 새로운 데이터 식별의 웹 기반 모니터링
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, List
import asyncio
import json
from datetime import datetime
import uvicorn

# 기존 크롤링 시스템 import
from src.services.crawler_service import CrawlingService
from src.repositories.sqlite_repository import SQLiteRepository
from src.crawlers.tax_tribunal_crawler import TaxTribunalCrawler
from src.crawlers.nts_authority_crawler import NTSAuthorityCrawler
from src.config.settings import GUI_CONFIG

# 웹 환경용 레거시 크롤러들 import (tkinter 의존성 없음)
try:
    from src.crawlers.web_legacy_crawlers import (
        crawl_nts_precedents, crawl_moef_site, crawl_mois_site, crawl_bai_site
    )
    LEGACY_CRAWLERS_AVAILABLE = True
    print("✅ 웹 환경용 레거시 크롤러 로드 성공")
except ImportError as e:
    print(f"❌ 웹 레거시 크롤러 import 실패: {e}")
    LEGACY_CRAWLERS_AVAILABLE = False
    
    # 더미 함수들로 대체
    def crawl_nts_precedents(**kwargs):
        raise NotImplementedError("웹 레거시 크롤러 사용 불가")
    
    def crawl_moef_site(**kwargs):
        raise NotImplementedError("웹 레거시 크롤러 사용 불가")
        
    def crawl_mois_site(**kwargs):
        raise NotImplementedError("웹 레거시 크롤러 사용 불가")
        
    def crawl_bai_site(**kwargs):
        raise NotImplementedError("웹 레거시 크롤러 사용 불가")

class LegacyCrawlerWrapper:
    """레거시 크롤러 함수를 클래스 인터페이스로 래핑"""
    def __init__(self, site_name, site_key, crawler_func, key_column):
        self.site_name = site_name
        self.site_key = site_key
        self.crawler_func = crawler_func
        self.key_column = key_column
    
    def get_site_name(self):
        return self.site_name
    
    def get_site_key(self):
        return self.site_key
    
    def get_key_column(self):
        return self.key_column
    
    def crawl(self, progress_callback=None, status_callback=None, **kwargs):
        return self.crawler_func(progress=progress_callback, status_message=status_callback, **kwargs)
    
    def validate_data(self, data):
        return not data.empty if data is not None else False


# FastAPI 앱 초기화
app = FastAPI(
    title="Tax Law Crawler Web Interface",
    description="세금 법령 크롤링 시스템 웹 인터페이스 - 누락없는 데이터 수집과 새로운 데이터 식별",
    version="1.0.0"
)

# 정적 파일 및 템플릿 설정
static_path = project_root / "src" / "web" / "static"
templates_path = project_root / "src" / "web" / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

# 크롤링 서비스 초기화
repository = SQLiteRepository()

# 기본 크롤러 (항상 사용 가능)
crawlers = {
    "tax_tribunal": TaxTribunalCrawler(),
    "nts_authority": NTSAuthorityCrawler(),
}

# 레거시 크롤러들 (tkinter 사용 가능한 경우에만 추가)
if LEGACY_CRAWLERS_AVAILABLE:
    crawlers.update({
        "nts_precedent": LegacyCrawlerWrapper(
            "국세청_판례", "nts_precedent", crawl_nts_precedents, "문서번호"
        ),
        "moef": LegacyCrawlerWrapper(
            "기획재정부", "moef", crawl_moef_site, "문서번호"
        ),
        "mois": LegacyCrawlerWrapper(
            "행정안전부", "mois", crawl_mois_site, "문서번호"
        ),
        "bai": LegacyCrawlerWrapper(
            "감사원", "bai", crawl_bai_site, "문서번호"
        )
    })
    print(f"✅ 모든 크롤러 사용 가능: {len(crawlers)}개")
else:
    print(f"⚠️  기본 크롤러만 사용 가능: {len(crawlers)}개 (레거시 크롤러 제외)")

crawling_service = CrawlingService(crawlers, repository)

# WebSocket 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                # 연결이 끊어진 경우 무시
                pass

manager = ConnectionManager()

# 사이트 정보 매핑 (동적으로 생성)
BASE_SITE_INFO = {
    "tax_tribunal": {"name": "조세심판원", "color": "#3B82F6"},
    "nts_authority": {"name": "국세청", "color": "#10B981"},
    "moef": {"name": "기획재정부", "color": "#8B5CF6"},
    "nts_precedent": {"name": "국세청 판례", "color": "#F59E0B"},
    "mois": {"name": "행정안전부", "color": "#EF4444"},
    "bai": {"name": "감사원", "color": "#6B7280"}
}

# 실제 사용 가능한 크롤러만 포함
SITE_INFO = {key: value for key, value in BASE_SITE_INFO.items() if key in crawlers}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sites/{site_key}", response_class=HTMLResponse)
async def site_detail(request: Request, site_key: str):
    """사이트별 상세 페이지"""
    if site_key not in SITE_INFO:
        raise HTTPException(status_code=404, detail="Site not found")
    
    site_info = SITE_INFO[site_key]
    return templates.TemplateResponse("site.html", {
        "request": request,
        "site_key": site_key,
        "site_name": site_info["name"]
    })

@app.get("/api/dashboard")
async def get_dashboard_data():
    """대시보드 데이터 조회"""
    try:
        dashboard_data = []
        
        for site_key, site_info in SITE_INFO.items():
            stats = repository.get_statistics(site_key)
            
            dashboard_data.append({
                "site_key": site_key,
                "site_name": site_info["name"],
                "color": site_info["color"],
                "total_count": stats.get("total_count", 0),
                "last_updated": stats.get("last_updated"),
                "status": "success" if stats.get("total_count", 0) > 0 else "empty"
            })
        
        return {
            "sites": dashboard_data,
            "last_refresh": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard data error: {str(e)}")

@app.get("/api/sites/{site_key}/data")
async def get_site_data(site_key: str, page: int = 1, limit: int = 50, search: str = ""):
    """사이트별 데이터 조회 (페이지네이션)"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        # 전체 데이터 로드
        data = repository.load_existing_data(site_key)
        
        # 검색 필터링
        if search:
            # 모든 텍스트 컬럼에서 검색
            text_columns = data.select_dtypes(include=['object']).columns
            mask = data[text_columns].astype(str).apply(
                lambda x: x.str.contains(search, case=False, na=False)
            ).any(axis=1)
            data = data[mask]
        
        # 페이지네이션
        total_count = len(data)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_data = data.iloc[start_idx:end_idx]
        
        # JSON 직렬화 가능한 형태로 변환
        records = page_data.to_dict('records')
        
        return {
            "site_key": site_key,
            "site_name": SITE_INFO[site_key]["name"],
            "data": records,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "total_pages": (total_count + limit - 1) // limit,
                "has_next": end_idx < total_count,
                "has_prev": page > 1
            },
            "search": search
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Site data error: {str(e)}")

@app.post("/api/crawl/{site_key}")
async def start_crawling(site_key: str):
    """개별 사이트 크롤링 시작"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        # 비동기적으로 크롤링 실행
        asyncio.create_task(run_crawling_task(site_key))
        
        return {
            "status": "started",
            "site_key": site_key,
            "site_name": SITE_INFO[site_key]["name"],
            "message": f"{SITE_INFO[site_key]['name']} 크롤링을 시작했습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawling start error: {str(e)}")

@app.post("/api/crawl/all")
async def start_all_crawling():
    """전체 사이트 크롤링 시작"""
    try:
        # 비동기적으로 전체 크롤링 실행
        asyncio.create_task(run_crawling_task("7"))  # choice = "7"은 전체 크롤링
        
        return {
            "status": "started",
            "message": "전체 사이트 크롤링을 시작했습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"All crawling start error: {str(e)}")

@app.get("/api/stats")
async def get_statistics():
    """전체 통계 정보"""
    try:
        total_records = 0
        site_stats = {}
        
        for site_key, site_info in SITE_INFO.items():
            stats = repository.get_statistics(site_key)
            site_count = stats.get("total_count", 0)
            total_records += site_count
            
            site_stats[site_key] = {
                "name": site_info["name"],
                "count": site_count,
                "last_updated": stats.get("last_updated")
            }
        
        return {
            "total_records": total_records,
            "site_stats": site_stats,
            "database_info": repository.get_database_info()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Statistics error: {str(e)}")

async def run_crawling_task(choice: str):
    """크롤링 작업 실행 (비동기)"""
    try:
        await manager.broadcast({
            "type": "crawl_start",
            "choice": choice,
            "timestamp": datetime.now().isoformat()
        })
        
        # 비동기 환경에서 실행
        import asyncio
        import concurrent.futures
        
        # 간단한 진행상황 콜백 (웹용)
        class WebProgress:
            def __init__(self):
                self.value = 0
            
            def update(self):
                pass
        
        class WebStatus:
            def __init__(self):
                self.text = ""
            
            def config(self, text):
                self.text = text
                print(f"[크롤링 상태] {text}")
            
            def update(self):
                pass
        
        def run_sync_crawling():
            """동기 크롤링 실행"""
            try:
                progress = WebProgress()
                status = WebStatus()
                
                # 크롤링 실행
                crawling_service.execute_crawling(choice, progress, status, is_periodic=False)
                return {"status": "success", "message": "크롤링 완료"}
                
            except Exception as e:
                print(f"크롤링 실행 오류: {e}")
                return {"status": "error", "error": str(e)}
        
        # ThreadPoolExecutor로 동기 함수를 비동기 실행
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_sync_crawling)
        
        # 결과에 따른 알림
        if result["status"] == "success":
            await manager.broadcast({
                "type": "crawl_complete",
                "choice": choice,
                "timestamp": datetime.now().isoformat()
            })
        else:
            await manager.broadcast({
                "type": "crawl_error",
                "error": result.get("error", "알 수 없는 오류"),
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        await manager.broadcast({
            "type": "crawl_error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

@app.websocket("/ws/crawl")
async def websocket_endpoint(websocket: WebSocket):
    """크롤링 상태 실시간 WebSocket"""
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 대기 (연결 유지용)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )