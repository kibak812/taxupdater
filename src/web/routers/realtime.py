from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.web.context import WebAppContext


def create_websocket_router(context: WebAppContext) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/crawl")
    async def websocket_endpoint(websocket: WebSocket):
        await context.manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            context.manager.disconnect(websocket)

    return router
