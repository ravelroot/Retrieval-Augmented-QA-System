from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from nexo import __version__, db, jobs
from nexo.api.deps import ApiError, get_users
from nexo.api.routes import router
from nexo.config import get_settings

WEB_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
log = logging.getLogger("nexo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    db.engine()
    get_users()
    pending = jobs.resume_pending()
    if pending:
        log.info("Retomando a indexação de %d documento(s).", pending)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Nexo", version=__version__, lifespan=lifespan, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)

    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError):
        return JSONResponse({"code": e.code, "message": e.message, "fields": e.fields}, status_code=e.status)

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
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/") and not request.url.path.endswith("/file"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(router)

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
