"""
FastAPI entrypoint for the Smart Component Storage backend.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs:
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import auth as auth_routes
from app.routes import inventory as inventory_routes
from app.routes import cabinet as cabinet_routes
from app.routes import alerts as alerts_routes
from app.routes import smart_logic as smart_logic_routes
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO)

# Creates tables if they don't exist yet
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        start_scheduler()
    except Exception as exc:
        logging.warning("Scheduler startup warning: %s", exc)
    yield
    # Shutdown
    try:
        stop_scheduler()
    except Exception as exc:
        logging.warning("Scheduler shutdown warning: %s", exc)


app = FastAPI(
    title="Smart Component Storage API",
    description="Backend for the smart cabinet + lifecycle management mobile/web app.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow web and mobile clients to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(inventory_routes.router)
app.include_router(inventory_routes.api_router)
app.include_router(cabinet_routes.router)
app.include_router(alerts_routes.router)
app.include_router(smart_logic_routes.router)


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """
    Real-time WebSocket telemetry subscription endpoint.
    Broadcasts instantaneous smoothed temperature/humidity readings and actuator commands
    to connected dashboards without client polling.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "smart-component-storage-api"}
