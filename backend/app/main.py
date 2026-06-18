from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.ws.manager import manager
from app.utils.logger import setup_logger

logger = setup_logger("hydrax")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HydraX starting up...")
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("HydraX shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.accounts import router as accounts_router
from app.api.copier import router as copier_router
from app.api.symbols import router as symbols_router
from app.api.trades import router as trades_router
from app.api.system import router as system_router
from app.api.servers import router as servers_router

app.include_router(accounts_router)
app.include_router(copier_router)
app.include_router(symbols_router)
app.include_router(trades_router)
app.include_router(system_router)
app.include_router(servers_router)


@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal(websocket, "pong", {"received": data})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )
