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
from src.crawlers.nts_precedent_crawler import NTSPrecedentCrawler
from src.config.settings import GUI_CONFIG
from src.config.logging_config import setup_logging, get_logger

# 새로운 모니터링 시스템 import
from src.services.scheduler_service import SchedulerService
from src.services.notification_service import NotificationService

# 로깅 시스템 초기화
setup_logging(log_level="INFO", log_to_file=True)
logger = get_logger(__name__)

# 웹 환경용 레거시 크롤러들 import (tkinter 의존성 없음)
try:
    from src.crawlers.web_legacy_crawlers import (
        crawl_moef_site, crawl_mois_site, crawl_bai_site
    )
    LEGACY_CRAWLERS_AVAILABLE = True
    logger.info("웹 환경용 레거시 크롤러 로드 성공")
except ImportError as e:
    logger.error(f"웹 레거시 크롤러 import 실패: {e}")
    LEGACY_CRAWLERS_AVAILABLE = False
    
    # 더미 함수들로 대체
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

# 기존 데이터베이스 스키마 업데이트 (웹 서버 시작 시)
logger.info("기존 데이터베이스 스키마 업데이트 중...")
repository.force_schema_update()

# 기본 크롤러 (항상 사용 가능)
crawlers = {
    "tax_tribunal": TaxTribunalCrawler(),
    "nts_authority": NTSAuthorityCrawler(),
    "nts_precedent": NTSPrecedentCrawler(),
}

# 레거시 크롤러들 (tkinter 사용 가능한 경우에만 추가)
if LEGACY_CRAWLERS_AVAILABLE:
    crawlers.update({
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
    logger.info(f"모든 크롤러 사용 가능: {len(crawlers)}개")
else:
    logger.warning(f"기본 크롤러만 사용 가능: {len(crawlers)}개 (레거시 크롤러 제외)")

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

# 새로운 모니터링 시스템 서비스 초기화 (WebSocket 매니저 전달)
scheduler_service = SchedulerService(crawling_service=crawling_service)
notification_service = NotificationService(websocket_manager=manager)

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
async def main_dashboard(request: Request):
    """메인 페이지 - 새로운 전문가용 대시보드"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def expert_dashboard(request: Request):
    """전문가용 대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/legacy", response_class=HTMLResponse)
async def legacy_dashboard(request: Request):
    """레거시 모니터링 시스템"""
    return templates.TemplateResponse("monitoring.html", {"request": request})

@app.get("/legacy/old", response_class=HTMLResponse)
async def legacy_old_dashboard(request: Request):
    """레거시 대시보드 페이지 (구 버전)"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data/{site_key}", response_class=HTMLResponse)
async def data_table_view(request: Request, site_key: str):
    """전문가용 데이터 목록 뷰"""
    if site_key not in SITE_INFO:
        raise HTTPException(status_code=404, detail="Site not found")
    
    site_info = SITE_INFO[site_key]
    return templates.TemplateResponse("data_table.html", {
        "request": request,
        "site_key": site_key,
        "site_name": site_info["name"],
        "site_color": site_info["color"]
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """설정 페이지"""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/sites/{site_key}", response_class=HTMLResponse)
async def site_detail(request: Request, site_key: str):
    """사이트별 상세 페이지 (레거시)"""
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
async def get_site_data(
    site_key: str, 
    page: int = 1, 
    limit: int = 50, 
    search: str = "",
    filter: str = None,  # 'recent' or 'range'
    days: int = None,    # for 'recent' filter
    start: str = None,   # for 'range' filter (YYYY-MM-DD)
    end: str = None      # for 'range' filter (YYYY-MM-DD)
):
    """사이트별 데이터 조회 (페이지네이션 + 시간 필터링)"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        # 필터 조건에 따라 데이터 로드
        if filter == "recent" and days:
            # 최근 N일 데이터만 로드
            data = repository.load_filtered_data(site_key, recent_days=days)
        elif filter == "range" and start and end:
            # 날짜 범위 데이터 로드
            data = repository.load_filtered_data(site_key, start_date=start, end_date=end)
        else:
            # 전체 데이터 로드 (메타데이터 포함)
            data = repository.load_existing_data(site_key, include_metadata=True)
        
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
        
        # 필터 정보 포함
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
            "search": search,
            "filter": filter_info
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Site data error: {str(e)}")

@app.post("/api/crawl/all")
async def start_all_crawling():
    """전체 사이트 크롤링 시작"""
    try:
        logger.info("전체 크롤링 API 함수 진입")
        logger.info(f"사용 가능한 크롤러: {list(crawlers.keys())}")
        logger.info(f"SITE_INFO 키: {list(SITE_INFO.keys())}")
        
        # 전체 크롤링 백그라운드 실행
        async def run_all_crawling():
            try:
                await manager.broadcast({
                    "type": "crawl_start",
                    "choice": "all",
                    "timestamp": datetime.now().isoformat()
                })
                
                import concurrent.futures
                
                def run_all_sync():
                    try:
                        logger.info("전체 크롤링 시작 (동기)")
                        # choice = "7"로 전체 크롤링 실행
                        crawling_service.execute_crawling("7", None, None, is_periodic=False)
                        logger.info("전체 크롤링 완료")
                        return {"status": "success"}
                    except Exception as e:
                        logger.error(f"전체 크롤링 오류: {e}")
                        return {"status": "error", "error": str(e)}
                
                # ThreadPoolExecutor로 실행
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    result = await loop.run_in_executor(executor, run_all_sync)
                
                # 완료 알림
                if result["status"] == "success":
                    await manager.broadcast({
                        "type": "crawl_complete",
                        "choice": "all",
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    await manager.broadcast({
                        "type": "crawl_error",
                        "error": result.get("error", "알 수 없는 오류"),
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"전체 크롤링 태스크 오류: {e}")
                await manager.broadcast({
                    "type": "crawl_error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        # 백그라운드로 전체 크롤링 실행
        asyncio.create_task(run_all_crawling())
        
        return {
            "status": "started",
            "message": "전체 사이트 크롤링을 시작했습니다."
        }
    
    except Exception as e:
        logger.error(f"전체 크롤링 시작 에러: {str(e)}")
        raise HTTPException(status_code=500, detail=f"All crawling start error: {str(e)}")

@app.post("/api/crawl/{site_key}")
async def start_crawling(site_key: str):
    """개별 사이트 크롤링 시작"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        # site_key를 choice로 변환하는 매핑
        site_to_choice_mapping = {
            "tax_tribunal": "1",
            "nts_authority": "2", 
            "moef": "3",
            "nts_precedent": "4",
            "mois": "5",
            "bai": "6"
        }
        
        choice = site_to_choice_mapping.get(site_key)
        if not choice:
            raise HTTPException(status_code=400, detail=f"Invalid site_key: {site_key}")
        
        # 비동기적으로 크롤링 실행
        asyncio.create_task(run_crawling_task(choice))
        
        return {
            "status": "started",
            "site_key": site_key,
            "site_name": SITE_INFO[site_key]["name"],
            "message": f"{SITE_INFO[site_key]['name']} 크롤링을 시작했습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawling start error: {str(e)}")

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

# === 새로운 모니터링 시스템 API 엔드포인트 ===

@app.get("/api/schedules")
async def get_schedules():
    """크롤링 스케줄 목록 조회"""
    try:
        status = scheduler_service.get_schedule_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄 조회 실패: {str(e)}")

@app.get("/api/schedules/{site_key}")
async def get_site_schedule(site_key: str):
    """특정 사이트 스케줄 상세 조회"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        status = scheduler_service.get_schedule_status(site_key)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"사이트 스케줄 조회 실패: {str(e)}")

@app.post("/api/schedules")
async def create_or_update_schedule(request: Request):
    """크롤링 스케줄 생성/수정"""
    try:
        data = await request.json()
        site_key = data.get("site_key")
        cron_expression = data.get("cron_expression")
        enabled = data.get("enabled", True)
        priority = data.get("priority", 0)
        notification_threshold = data.get("notification_threshold", 1)
        
        if not site_key or not cron_expression:
            raise HTTPException(status_code=400, detail="site_key와 cron_expression이 필요합니다")
        
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        success = scheduler_service.add_crawl_schedule(
            site_key, cron_expression, enabled, priority, notification_threshold
        )
        
        if success:
            return {
                "status": "success",
                "message": f"{SITE_INFO[site_key]['name']} 스케줄이 업데이트되었습니다",
                "site_key": site_key
            }
        else:
            raise HTTPException(status_code=500, detail="스케줄 업데이트 실패")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄 생성/수정 실패: {str(e)}")

@app.delete("/api/schedules/{site_key}")
async def delete_schedule(site_key: str):
    """크롤링 스케줄 삭제(비활성화)"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        success = scheduler_service.remove_crawl_schedule(site_key)
        
        if success:
            return {
                "status": "success",
                "message": f"{SITE_INFO[site_key]['name']} 스케줄이 비활성화되었습니다"
            }
        else:
            raise HTTPException(status_code=500, detail="스케줄 삭제 실패")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄 삭제 실패: {str(e)}")

@app.post("/api/schedules/{site_key}/trigger")
async def trigger_manual_crawl(site_key: str, request: Request):
    """수동 크롤링 트리거"""
    try:
        if site_key not in SITE_INFO:
            raise HTTPException(status_code=404, detail="Site not found")
        
        data = await request.json()
        delay_seconds = data.get("delay_seconds", 0)
        
        success = scheduler_service.trigger_manual_crawl(site_key, delay_seconds)
        
        if success:
            return {
                "status": "success",
                "message": f"{SITE_INFO[site_key]['name']} 수동 크롤링이 예약되었습니다",
                "delay_seconds": delay_seconds
            }
        else:
            raise HTTPException(status_code=500, detail="수동 크롤링 트리거 실패")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수동 크롤링 트리거 실패: {str(e)}")

@app.get("/api/notifications")
async def get_notifications(
    site_key: str = None, 
    notification_type: str = None, 
    limit: int = 50, 
    unread_only: bool = False
):
    """알림 목록 조회"""
    try:
        notifications = await notification_service.get_notifications(
            site_key, notification_type, limit, unread_only
        )
        return {
            "notifications": notifications,
            "total_count": len(notifications)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알림 조회 실패: {str(e)}")

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    """알림 읽음 처리"""
    try:
        success = await notification_service.mark_notification_read(notification_id)
        
        if success:
            return {
                "status": "success",
                "message": "알림이 읽음 처리되었습니다"
            }
        else:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알림 읽음 처리 실패: {str(e)}")

@app.get("/api/notifications/stats")
async def get_notification_stats(site_key: str = None):
    """알림 통계 조회"""
    try:
        stats = await notification_service.get_notification_stats(site_key)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알림 통계 조회 실패: {str(e)}")

@app.get("/api/sites/recent-counts")
async def get_recent_data_counts(hours: int = 24):
    """각 사이트별 최근 데이터 개수 조회 (각 사이트 테이블 기반)"""
    try:
        # Repository에서 최근 데이터 개수 조회
        counts = repository.get_recent_data_counts(hours)
        
        # 사이트 정보와 함께 반환
        result = {}
        for site_key, count in counts.items():
            result[site_key] = {
                "count": count,
                "site_name": SITE_INFO.get(site_key, {}).get("name", site_key)
            }
        
        return {
            "recent_counts": result,
            "hours": hours,
            "total_new_items": sum(counts.values())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"최근 데이터 개수 조회 실패: {str(e)}")

@app.get("/api/new-data")
async def get_new_data(
    site_key: str = None, 
    hours: int = 24, 
    limit: int = 100
):
    """새로운 데이터 조회"""
    try:
        import sqlite3
        from datetime import timedelta
        
        # 조회 시간 범위 계산
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(repository.db_path) as conn:
            cursor = conn.cursor()
            
            # 쿼리 구성
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
                
                # JSON 필드 파싱
                if data_row['tags']:
                    data_row['tags'] = json.loads(data_row['tags'])
                if data_row['metadata']:
                    data_row['metadata'] = json.loads(data_row['metadata'])
                
                # 사이트 이름 추가
                data_row['site_name'] = SITE_INFO.get(data_row['site_key'], {}).get('name', data_row['site_key'])
                
                new_data.append(data_row)
        
        return {
            "new_data": new_data,
            "total_count": len(new_data),
            "hours": hours,
            "cutoff_time": cutoff_time.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"새로운 데이터 조회 실패: {str(e)}")

@app.get("/api/system-status")
async def get_system_status():
    """시스템 상태 조회"""
    try:
        import sqlite3
        
        with sqlite3.connect(repository.db_path) as conn:
            cursor = conn.cursor()
            
            # 시스템 상태 조회
            cursor.execute("""
                SELECT site_key, component_type, status, last_check, last_success,
                       last_error, error_message, consecutive_errors, health_score,
                       uptime_seconds, response_time_ms
                FROM system_status
                ORDER BY site_key, component_type
            """)
            
            columns = [desc[0] for desc in cursor.description]
            system_status = []
            
            for row in cursor.fetchall():
                status_row = dict(zip(columns, row))
                # 사이트 이름 추가
                status_row['site_name'] = SITE_INFO.get(status_row['site_key'], {}).get('name', status_row['site_key'])
                system_status.append(status_row)
        
        # 스케줄러 상태 추가
        scheduler_status = {
            "scheduler_running": scheduler_service.is_running(),
            "active_jobs": len(scheduler_service.scheduler.get_jobs()) if scheduler_service.is_running() else 0
        }
        
        return {
            "system_status": system_status,
            "scheduler_status": scheduler_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시스템 상태 조회 실패: {str(e)}")

@app.get("/api/job-history")
async def get_job_history(site_key: str = None, limit: int = 50):
    """작업 이력 조회"""
    try:
        history = scheduler_service.get_job_history(site_key, limit)
        
        # 사이트 이름 추가
        for item in history:
            item['site_name'] = SITE_INFO.get(item['site_key'], {}).get('name', item['site_key'])
        
        return {
            "job_history": history,
            "total_count": len(history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"작업 이력 조회 실패: {str(e)}")

@app.post("/api/scheduler/start")
async def start_scheduler():
    """스케줄러 시작"""
    try:
        if scheduler_service.is_running():
            return {
                "status": "already_running",
                "message": "스케줄러가 이미 실행 중입니다"
            }
        
        scheduler_service.start()
        
        # 시스템 알림 발송
        await notification_service.send_system_notification(
            "스케줄러가 시작되었습니다", "normal", "system"
        )
        
        return {
            "status": "started",
            "message": "스케줄러가 시작되었습니다"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 시작 실패: {str(e)}")

@app.post("/api/scheduler/stop")
async def stop_scheduler():
    """스케줄러 중지"""
    try:
        if not scheduler_service.is_running():
            return {
                "status": "already_stopped",
                "message": "스케줄러가 이미 중지되어 있습니다"
            }
        
        scheduler_service.stop()
        
        # 시스템 알림 발송
        await notification_service.send_system_notification(
            "스케줄러가 중지되었습니다", "normal", "system"
        )
        
        return {
            "status": "stopped",
            "message": "스케줄러가 중지되었습니다"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 중지 실패: {str(e)}")

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
        
        # WebSocket 연동 진행상황 콜백 (Thread-safe 실시간 웹 피드백)
        class WebSocketProgress:
            def __init__(self, loop, manager, choice):
                self.value = 0
                self.loop = loop
                self.manager = manager
                self.choice = choice
            
            def update(self):
                # Thread-safe WebSocket 전송
                try:
                    message = {
                        "type": "crawl_progress",
                        "choice": self.choice,
                        "progress": self.value,
                        "timestamp": datetime.now().isoformat()
                    }
                    # asyncio.run_coroutine_threadsafe로 비동기 작업 스케줄링
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message), 
                        self.loop
                    )
                except Exception as e:
                    logger.error(f"진행률 WebSocket 전송 오류: {e}")
        
        class WebSocketStatus:
            def __init__(self, loop, manager, choice):
                self.text = ""
                self.loop = loop
                self.manager = manager
                self.choice = choice
            
            def config(self, text):
                self.text = text
                # Thread-safe WebSocket 전송
                try:
                    message = {
                        "type": "crawl_status",
                        "choice": self.choice,
                        "status": text,
                        "timestamp": datetime.now().isoformat()
                    }
                    # asyncio.run_coroutine_threadsafe로 비동기 작업 스케줄링
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message), 
                        self.loop
                    )
                except Exception as e:
                    logger.error(f"상태 WebSocket 전송 오류: {e}")
            
            def update(self):
                # 상태 업데이트 시에도 전송
                if self.text:
                    self.config(self.text)
        
        def run_sync_crawling():
            """동기 크롤링 실행 (Thread-safe WebSocket 연동)"""
            try:
                # 현재 이벤트 루프를 가져와서 WebSocket 연동 진행상황 객체 생성
                progress = WebSocketProgress(loop, manager, choice)
                status = WebSocketStatus(loop, manager, choice)
                
                logger.info(f"크롤링 실행 시작: choice={choice}")
                
                # 크롤링 실행
                crawling_service.execute_crawling(choice, progress, status, is_periodic=False)
                logger.info(f"크롤링 실행 완료: choice={choice}")
                return {"status": "success", "message": "크롤링 완료"}
                
            except Exception as e:
                logger.error(f"크롤링 실행 오류 (choice={choice}): {e}")
                logger.error(f"오류 타입: {type(e).__name__}")
                import traceback
                logger.error(f"스택 트레이스: {traceback.format_exc()}")
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

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 이벤트"""
    logger.info("FastAPI 서버 시작")
    logger.info("웹 인터페이스: http://localhost:8001")
    
    # 스케줄러 시작
    try:
        scheduler_service.start()
        logger.info("자동 스케줄러 시작됨")
        
        # 시스템 시작 알림
        await notification_service.send_system_notification(
            "모니터링 시스템이 시작되었습니다", "normal", "system"
        )
    except Exception as e:
        logger.error(f"스케줄러 시작 실패: {e}")

@app.on_event("shutdown") 
async def shutdown_event():
    """서버 종료 시 이벤트"""
    logger.info("FastAPI 서버 종료")
    
    # 스케줄러 중지
    try:
        if scheduler_service.is_running():
            scheduler_service.stop()
            logger.info("스케줄러 정상 종료됨")
    except Exception as e:
        logger.error(f"스케줄러 종료 실패: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )