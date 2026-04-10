from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager
from pathlib import Path
from app.core.config import settings
from app.db.database import create_tables
from app.api.routes import auth, health, chat, chat_history
from app.services.redis.redis_services import redis_service  # add import

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGMA_UI_FILE = PROJECT_ROOT / "frontend" / "figma_mock" / "agentic_hub_usecase_ui.html"
AUTH_UI_FILE = PROJECT_ROOT / "frontend" / "figma_mock" / "agentic_hub_auth.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await create_tables()
    print("✅ Database tables created")
    await redis_service.connect()          # ← add this
    print("✅ Redis connected")
    yield
    await redis_service.disconnect()       # ← add this
    print("👋 Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-Agent LLM Chatbot with Multimodal Support",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────
app.include_router(auth.router,          prefix="/api/v1")
app.include_router(health.router)
app.include_router(chat.router,          prefix="/api/v1/chat",  tags=["Chat"])
app.include_router(chat_history.router,  prefix="/api/v1/chat",  tags=["Chat History"])


@app.get("/")
async def root():
    return RedirectResponse(url="/ui-final", status_code=307)


@app.get("/ui-final")
async def ui_final():
    if FIGMA_UI_FILE.exists():
        return FileResponse(str(FIGMA_UI_FILE))
    return {
        "error": "UI final workspace not found",
        "expected_path": str(FIGMA_UI_FILE)
    }


@app.get("/ui-prototype")
async def ui_prototype():
    return await ui_final()


@app.get("/ui-auth")
async def ui_auth():
    if AUTH_UI_FILE.exists():
        return FileResponse(str(AUTH_UI_FILE))
    return {
        "error": "Auth UI not found",
        "expected_path": str(AUTH_UI_FILE)
    }