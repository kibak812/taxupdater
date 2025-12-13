"""
크롤링 라우터

엔드포인트:
- POST /api/crawl/all : 전체 크롤링 시작
- POST /api/crawl/{site_key} : 개별 사이트 크롤링
- WS /ws/crawl : 실시간 크롤링 상태 WebSocket
"""

from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import json

from src.config.sites import get_choice_by_key


def create_crawl_router(
    site_info: Dict[str, Dict],
    crawling_service: Any,
    scheduler_service: Optional[Any] = None,
    ws_manager: Optional[Any] = None
) -> APIRouter:
    """
    크롤링 라우터 생성

    Args:
        site_info: 사이트 정보 매핑
        crawling_service: 크롤링 서비스
        scheduler_service: 스케줄러 서비스 (선택)
        ws_manager: WebSocket 연결 관리자 (선택)
    """
    router = APIRouter()

    # site_key → choice 변환은 get_choice_by_key() 함수 사용

    async def run_crawling_task(choice: str):
        """크롤링 작업 실행 (비동기)"""
        if not ws_manager:
            return

        try:
            await ws_manager.broadcast({
                "type": "crawl_start",
                "choice": choice,
                "timestamp": datetime.now().isoformat()
            })

            import concurrent.futures

            class WebSocketProgress:
                def __init__(self, loop, manager, choice):
                    self.value = 0
                    self.loop = loop
                    self.manager = manager
                    self.choice = choice

                def update(self):
                    try:
                        message = {
                            "type": "crawl_progress",
                            "choice": self.choice,
                            "progress": self.value,
                            "timestamp": datetime.now().isoformat()
                        }
                        asyncio.run_coroutine_threadsafe(
                            self.manager.broadcast(message),
                            self.loop
                        )
                    except Exception:
                        pass

            class WebSocketStatus:
                def __init__(self, loop, manager, choice):
                    self.text = ""
                    self.loop = loop
                    self.manager = manager
                    self.choice = choice

                def config(self, text):
                    self.text = text
                    try:
                        message = {
                            "type": "crawl_status",
                            "choice": self.choice,
                            "status": text,
                            "timestamp": datetime.now().isoformat()
                        }
                        asyncio.run_coroutine_threadsafe(
                            self.manager.broadcast(message),
                            self.loop
                        )
                    except Exception:
                        pass

                def update(self):
                    if self.text:
                        self.config(self.text)

            def run_sync_crawling():
                try:
                    progress = WebSocketProgress(loop, ws_manager, choice)
                    status = WebSocketStatus(loop, ws_manager, choice)
                    crawling_service.execute_crawling(choice, progress, status, is_periodic=False)
                    return {"status": "success"}
                except Exception as e:
                    return {"status": "error", "error": str(e)}

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_sync_crawling)

            if result["status"] == "success":
                await ws_manager.broadcast({
                    "type": "crawl_complete",
                    "choice": choice,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                await ws_manager.broadcast({
                    "type": "crawl_error",
                    "error": result.get("error", "알 수 없는 오류"),
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            await ws_manager.broadcast({
                "type": "crawl_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    @router.post("/api/crawl/all")
    async def start_all_crawling():
        """전체 사이트 크롤링 시작"""
        try:
            async def run_all_crawling():
                try:
                    if ws_manager:
                        await ws_manager.broadcast({
                            "type": "crawl_start",
                            "choice": "all",
                            "timestamp": datetime.now().isoformat()
                        })

                    import concurrent.futures

                    def run_all_sync():
                        try:
                            result = scheduler_service._execute_all_sites_crawl()
                            return {"status": "success", "result": result}
                        except Exception as e:
                            return {"status": "error", "error": str(e)}

                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = await loop.run_in_executor(executor, run_all_sync)

                    if ws_manager:
                        if result["status"] == "success":
                            await ws_manager.broadcast({
                                "type": "crawl_complete",
                                "choice": "all",
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            await ws_manager.broadcast({
                                "type": "crawl_error",
                                "error": result.get("error", "알 수 없는 오류"),
                                "timestamp": datetime.now().isoformat()
                            })

                except Exception as e:
                    if ws_manager:
                        await ws_manager.broadcast({
                            "type": "crawl_error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        })

            asyncio.create_task(run_all_crawling())

            return {
                "status": "started",
                "message": "전체 사이트 크롤링을 시작했습니다."
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"All crawling start error: {str(e)}")

    @router.post("/api/crawl/{site_key}")
    async def start_crawling(site_key: str):
        """개별 사이트 크롤링 시작"""
        try:
            if site_key not in site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            try:
                choice = get_choice_by_key(site_key)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid site_key: {site_key}")

            if scheduler_service:
                success = scheduler_service.trigger_manual_crawl(site_key)
                if not success:
                    raise HTTPException(status_code=500, detail="크롤링 실행 실패")
            else:
                asyncio.create_task(run_crawling_task(choice))

            return {
                "status": "started",
                "site_key": site_key,
                "site_name": site_info[site_key]["name"],
                "message": f"{site_info[site_key]['name']} 크롤링을 시작했습니다."
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Crawling start error: {str(e)}")

    return router


def create_websocket_handler(ws_manager: Any):
    """WebSocket 핸들러 생성 (별도 함수)"""

    async def websocket_endpoint(websocket: WebSocket):
        """크롤링 상태 실시간 WebSocket"""
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return websocket_endpoint
