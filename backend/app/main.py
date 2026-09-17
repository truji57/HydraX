from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings, get_version
from app.database import init_db
from app.ws.manager import manager
from app.utils.logger import setup_logger
from app.utils.events import record_event_standalone

logger = setup_logger("hydrax")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HydraX starting up...")
    init_db()
    logger.info("Database initialized")
    record_event_standalone("app_start", {"message": "HydraX iniciado"})
    yield
    logger.info("HydraX shutting down...")
    record_event_standalone("app_stop", {"message": "HydraX detenido"})


app = FastAPI(title="HydraX", version=get_version(), lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.accounts import router as accounts_router
from app.api.copier import router as copier_router
from app.api.trades import router as trades_router
from app.api.system import router as system_router
from app.api.templates import router as templates_router
from app.api.events import router as events_router
from app.api.servers import router as servers_router
from app.api.symbols import router as symbols_router

app.include_router(accounts_router)
app.include_router(copier_router)
app.include_router(trades_router)
app.include_router(system_router)
app.include_router(templates_router)
app.include_router(events_router)
app.include_router(servers_router)
app.include_router(symbols_router)


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
    return {"app": "HydraX", "version": get_version(), "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=settings.DEBUG)
