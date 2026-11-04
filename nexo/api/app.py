from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from nexo import __version__, context, db, jobs, maintenance
from nexo.api.agents import router as agents_router
from nexo.api.deps import ApiError, get_users
from nexo.api.routes import router
from nexo.api.system import router as system_router
from nexo.api.whatsapp import router as whatsapp_router
from nexo.config import get_settings
from nexo.rag.engine import get_engine

WEB_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
log = logging.getLogger("nexo")
access = logging.getLogger("nexo.access")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

TAGS = (
    ("/api/auth", "Contas e sessão"),
    ("/api/users", "Contas e sessão"),
    ("/api/bases", "Bases de conhecimento"),
    ("/api/documents", "Documentos"),
    ("/api/formats", "Documentos"),
    ("/api/bots", "Agentes"),
    ("/api/conversations", "Conversas"),
    ("/api/messages", "Conversas"),
    ("/api/ask", "Perguntas e busca"),
    ("/api/search", "Perguntas e busca"),
    ("/api/metrics", "Painel de qualidade"),
    ("/api/keys", "Integrações"),
    ("/api/webhooks", "Integrações"),
    ("/api/whatsapp", "WhatsApp"),
    ("/api/system", "Sistema e manutenção"),
    ("/api/audit", "Sistema e manutenção"),
    ("/api/health", "Saúde"),
)

DESCRIPTION = ("API do Nexo: agentes de IA que respondem só com a própria base de conhecimento, citando a página. "
               "Autentique com `Authorization: Bearer <token>` ou com uma chave de API em `X-API-Key`.")


class Stats:
    def __init__(self):
        self.started = time.time()
        self.requests: Counter[str] = Counter()
        self.duration_ms = 0.0
        self._lock = threading.Lock()

    def add(self, status: int, ms: float) -> None:
        with self._lock:
            self.requests[f"{status // 100}xx"] += 1
            self.duration_ms += ms


def _tag(path: str) -> str | None:
    return next((tag for prefix, tag in TAGS if path == prefix or path.startswith(prefix + "/")), None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db.engine()
    get_users()
    stamped = jobs.stamp_unsigned(get_engine(settings).signature())
    if stamped:
        log.info("Configuração de índice registrada em %d documento(s).", stamped)
    pending = jobs.resume_pending()
    if pending:
        log.info("Retomando a indexação de %d documento(s).", pending)
    retention = maintenance.Retention(settings)
    retention.start()
    try:
        yield
    finally:
        retention.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Nexo", version=__version__, description=DESCRIPTION, lifespan=lifespan, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)
    app.state.stats = Stats()

    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError):
        return JSONResponse({"code": e.code, "message": e.message, "fields": e.fields}, status_code=e.status,
                            headers=e.headers or None)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError):
        fields = {}
        for err in e.errors():
            loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
            fields.setdefault(".".join(loc) or "body", "Valor inválido.")
        return JSONResponse({"code": "VALIDATION", "message": "Revise os campos destacados.", "fields": fields},
                            status_code=422)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        ip = forwarded or (request.client.host if request.client else None)
        id_token = context.request_id.set(request_id)
        ip_token = context.client_ip.set(ip)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            ms = (time.perf_counter() - started) * 1000
            app.state.stats.add(status, ms)
            if request.url.path.startswith("/api/"):
                access.info("%s %s %s %.0f ms", request.method, request.url.path, status, ms,
                            extra={"request_id": request_id, "method": request.method, "path": request.url.path,
                                   "status": status, "duration_ms": round(ms, 1), "ip": ip})
            context.request_id.reset(id_token)
            context.client_ip.reset(ip_token)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/") and not request.url.path.endswith("/file"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    if settings.cors_list:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=False,
                           allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                           allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
                           expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"], max_age=600)

    for part in (router, agents_router, whatsapp_router, system_router):
        for route in part.routes:
            if isinstance(route, APIRoute) and not route.tags:
                tag = _tag(route.path)
                if tag:
                    route.tags = [tag]
        app.include_router(part)

    if WEB_DIR.exists():
        assets = WEB_DIR / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"code": "NOT_FOUND", "message": "Rota não encontrada.", "fields": {}},
                                    status_code=404)
            target = (WEB_DIR / path).resolve()
            if path and target.is_file() and WEB_DIR in target.parents:
                return FileResponse(target)
            return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()
