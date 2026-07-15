import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.api.router import router
from app.api.capabilities import router as capabilities_router
from app.api.web_imports import router as web_imports_router
from app.api.model_settings import router as model_settings_router
from app.api.knowledge_graph import router as knowledge_graph_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import engine
from app.integrations.ollama import OllamaClient
from app.integrations.milvus import MilvusIndex
from app.services.model_warmup import warmup_models

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.model_warmup = await warmup_models()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", description="AI教育智能体 MVP API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details, "request_id": request.headers.get("X-Request-ID", "")}},
    )


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/ready", tags=["health"])
async def ready():
    checks = {}
    try:
        with engine.connect() as conn: conn.execute(text("SELECT 1"))
        checks["mysql"] = {"ok": True}
    except Exception as exc: checks["mysql"] = {"ok": False, "error": str(exc)}
    try: checks["models"] = await OllamaClient().health()
    except Exception as exc: checks["models"] = {"ok": False, "error": str(exc)}
    try: checks["milvus"] = MilvusIndex().health()
    except Exception as exc: checks["milvus"] = {"ok": False, "error": str(exc)}
    checks["model_warmup"] = getattr(app.state, "model_warmup", {"ok": False, "error": "启动预热尚未完成"})
    ok = all(item.get("ok") for item in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "degraded", "checks": checks})


app.include_router(router, prefix=settings.api_prefix)
app.include_router(capabilities_router, prefix=settings.api_prefix)
app.include_router(web_imports_router, prefix=settings.api_prefix)
app.include_router(model_settings_router, prefix=settings.api_prefix)
app.include_router(knowledge_graph_router, prefix=settings.api_prefix)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


frontend_dist = Path(__file__).parents[2] / "frontend" / "dist"
if settings.serve_frontend and frontend_dist.exists():
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
