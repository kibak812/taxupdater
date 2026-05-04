import asyncio
import concurrent.futures
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.config.sites import get_choice_by_key
from src.web.context import WebAppContext


def create_crawl_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()
    logger = context.logger

    @router.post("/api/crawl/all")
    async def start_all_crawling():
        try:
            logger.info("전체 크롤링 API 함수 진입")
            logger.info(f"사용 가능한 크롤러: {list(context.crawlers.keys())}")
            logger.info(f"SITE_INFO 키: {list(context.site_info.keys())}")

            async def run_all_crawling():
                try:
                    await context.manager.broadcast(
                        {
                            "type": "crawl_start",
                            "choice": "all",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    def run_all_sync():
                        try:
                            logger.info("전체 크롤링 시작 (동기)")
                            result = context.scheduler_service._execute_all_sites_crawl()
                            logger.info("전체 크롤링 완료")
                            return {"status": "success", "result": result}
                        except Exception as e:
                            logger.error(f"전체 크롤링 오류: {e}")
                            return {"status": "error", "error": str(e)}

                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = await loop.run_in_executor(executor, run_all_sync)

                    if result["status"] == "success":
                        await context.manager.broadcast(
                            {
                                "type": "crawl_complete",
                                "choice": "all",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    else:
                        await context.manager.broadcast(
                            {
                                "type": "crawl_error",
                                "error": result.get("error", "알 수 없는 오류"),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                except Exception as e:
                    logger.error(f"전체 크롤링 태스크 오류: {e}")
                    await context.manager.broadcast(
                        {
                            "type": "crawl_error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            asyncio.create_task(run_all_crawling())

            return {
                "status": "started",
                "message": "전체 사이트 크롤링을 시작했습니다.",
            }
        except Exception as e:
            logger.error(f"전체 크롤링 시작 에러: {str(e)}")
            raise HTTPException(status_code=500, detail=f"All crawling start error: {str(e)}")

    @router.post("/api/crawl/{site_key}")
    async def start_crawling(site_key: str):
        try:
            if site_key not in context.site_info:
                raise HTTPException(status_code=404, detail="Site not found")

            try:
                choice = get_choice_by_key(site_key)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid site_key: {site_key}")

            if context.scheduler_service:
                success = context.scheduler_service.trigger_manual_crawl(site_key)
                if not success:
                    raise HTTPException(status_code=500, detail="크롤링 실행 실패")
            else:
                asyncio.create_task(run_crawling_task(choice, context))

            return {
                "status": "started",
                "site_key": site_key,
                "site_name": context.site_info[site_key]["name"],
                "message": f"{context.site_info[site_key]['name']} 크롤링을 시작했습니다.",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Crawling start error: {str(e)}")

    return router


async def run_crawling_task(choice: str, context: WebAppContext):
    """Run a crawl task in a thread while broadcasting progress over WebSocket."""
    logger = context.logger

    try:
        await context.manager.broadcast(
            {
                "type": "crawl_start",
                "choice": choice,
                "timestamp": datetime.now().isoformat(),
            }
        )

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
                        "timestamp": datetime.now().isoformat(),
                    }
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message),
                        self.loop,
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
                try:
                    message = {
                        "type": "crawl_status",
                        "choice": self.choice,
                        "status": text,
                        "timestamp": datetime.now().isoformat(),
                    }
                    asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(message),
                        self.loop,
                    )
                except Exception as e:
                    logger.error(f"상태 WebSocket 전송 오류: {e}")

            def update(self):
                if self.text:
                    self.config(self.text)

        def run_sync_crawling():
            try:
                progress = WebSocketProgress(loop, context.manager, choice)
                status = WebSocketStatus(loop, context.manager, choice)

                logger.info(f"크롤링 실행 시작: choice={choice}")
                context.crawling_service.execute_crawling(choice, progress, status, is_periodic=False)
                logger.info(f"크롤링 실행 완료: choice={choice}")
                return {"status": "success", "message": "크롤링 완료"}
            except Exception as e:
                logger.error(f"크롤링 실행 오류 (choice={choice}): {e}")
                logger.error(f"오류 타입: {type(e).__name__}")
                import traceback

                logger.error(f"스택 트레이스: {traceback.format_exc()}")
                return {"status": "error", "error": str(e)}

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_sync_crawling)

        if result["status"] == "success":
            await context.manager.broadcast(
                {
                    "type": "crawl_complete",
                    "choice": choice,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            await context.manager.broadcast(
                {
                    "type": "crawl_error",
                    "error": result.get("error", "알 수 없는 오류"),
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        await context.manager.broadcast(
            {
                "type": "crawl_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
