from __future__ import annotations

import csv
import io
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import __version__, audit, db, maintenance, onboarding, runtime
from nexo.api import schemas as sc
from nexo.api.deps import ApiError, Principal, current_user, get_users, must_change_password
from nexo.config import Settings, get_settings
from nexo.rag import providers
from nexo.rag.engine import get_engine
from nexo.users import UserStore

router = APIRouter(prefix="/api")
ADMIN = "Só administradores podem usar esta área."


def _admin(p: Principal) -> None:
    if not p.is_admin:
        raise ApiError(403, "FORBIDDEN", ADMIN)


def _fixed(settings: Settings) -> dict[str, str]:
    info = providers.describe(settings)
    return {
        "Banco vetorial": f"{info['vector_store']}, coleção {info['collection']}",
        "Banco relacional": "SQLite" if settings.sqlalchemy_url.startswith("sqlite") else settings.sqlalchemy_url.split(":")[0],
        "Formato dos registros": settings.log_format,
        "Origens liberadas (CORS)": ", ".join(settings.cors_list) or "nenhuma",
        "Links da rede interna": "liberados" if settings.allow_private_urls else "bloqueados",
    }


def _outdated(database: Session, settings: Settings) -> int:
    signature = providers.index_signature(settings)
    return int(database.scalar(select(func.count()).select_from(db.DocumentRow)
                               .where(db.DocumentRow.status == "READY", db.DocumentRow.index_signature.is_not(None),
                                      db.DocumentRow.index_signature != signature)) or 0)


def _settings_out(database: Session, settings: Settings) -> sc.SettingsOut:
    return sc.SettingsOut(items=[sc.SettingItem(**i) for i in runtime.describe(settings)], fixed=_fixed(settings),
                          outdated=_outdated(database, settings))


@router.get("/system/settings", response_model=sc.SettingsOut)
def read_settings(p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                  database: Session = Depends(db.get_db)):
    _admin(p)
    return _settings_out(database, settings)


@router.put("/system/settings", response_model=sc.SettingsChanged)
def write_settings(body: sc.SettingsPatch, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                   database: Session = Depends(db.get_db)):
    _admin(p)
    try:
        changed = runtime.update(settings, body.values, p.username)
    except runtime.AdjustError as e:
        raise ApiError(400, "INVALID_SETTINGS", "Revise os ajustes destacados.", e.fields)
    rebuilt = _apply(settings, changed, p.username)
    if changed:
        audit.record("settings.update", "settings", None, _visible(settings, changed), actor=p.username)
    out = _settings_out(database, settings)
    reindex = any(runtime.BY_NAME[n].reindex for n in changed)
    return sc.SettingsChanged(**out.model_dump(), changed=changed, reindex_needed=reindex and out.outdated > 0, rebuilt=rebuilt)


@router.post("/system/settings/reset", response_model=sc.SettingsChanged)
def reset_settings(body: sc.SettingsResetIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                   database: Session = Depends(db.get_db)):
    _admin(p)
    changed = runtime.reset(settings, p.username, body.names)
    rebuilt = _apply(settings, changed, p.username)
    audit.record("settings.reset", "settings", None, {"names": changed}, actor=p.username)
    out = _settings_out(database, settings)
    reindex = any(runtime.BY_NAME[n].reindex for n in changed)
    return sc.SettingsChanged(**out.model_dump(), changed=changed, reindex_needed=reindex and out.outdated > 0, rebuilt=rebuilt)


def _visible(settings: Settings, names: list[str]) -> dict:
    return {k: ("(alterada)" if k in runtime.SECRETS else getattr(settings, k)) for k in names}


def _apply(settings: Settings, changed: list[str], who: str) -> int:
    get_engine(settings).refresh(changed)
    if not set(changed) & set(runtime.WIPE):
        return 0
    queued = maintenance.sync_vector_space(settings)
    if queued:
        audit.record("system.rebuild", "system", None, {"documentos": queued, "embeddings": settings.embed_model}, actor=who)
    return queued


@router.post("/system/providers/test", response_model=sc.ProviderTestOut)
def test_provider(body: sc.ProviderTestIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    try:
        candidate, fields = runtime.trial(settings, body.values)
    except runtime.AdjustError as e:
        raise ApiError(400, "INVALID_SETTINGS", "Revise os ajustes destacados.", e.fields)
    if fields:
        raise ApiError(400, "INVALID_SETTINGS", "Revise os ajustes destacados.", fields)
    return sc.ProviderTestOut(target=body.target, **providers.probe(body.target, candidate))


@router.get("/system/providers/ollama-models", response_model=sc.OllamaModelsOut)
def ollama_models(url: str = Query("", max_length=300), p: Principal = Depends(current_user),
                  settings: Settings = Depends(get_settings)):
    _admin(p)
    try:
        candidate, fields = runtime.trial(settings, {"ollama_url": url} if url.strip() else {})
    except runtime.AdjustError as e:
        raise ApiError(400, "INVALID_SETTINGS", "Revise o endereço do Ollama.", e.fields)
    if fields:
        raise ApiError(400, "INVALID_SETTINGS", "Revise o endereço do Ollama.", fields)
    names, error = maintenance.ollama_models(candidate)
    return sc.OllamaModelsOut(url=candidate.ollama_url, models=sorted(names or []), error=error)


def _setup_out(settings: Settings, users: UserStore, database: Session, username: str) -> sc.SetupOut:
    steps = onboarding.steps(settings, users, database)
    user = users.get(username)
    done_at = onboarding.done_at(settings)
    return sc.SetupOut(done=bool(done_at), done_at=done_at, public_url=settings.public_url, llm_provider=settings.llm_provider,
                       must_change_password=bool(user and must_change_password(user, users, settings)),
                       steps=[sc.SetupStep(**x) for x in steps], completed=sum(1 for x in steps if x["done"]), total=len(steps))


@router.get("/system/setup", response_model=sc.SetupOut)
def setup_state(p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                users: UserStore = Depends(get_users), database: Session = Depends(db.get_db)):
    _admin(p)
    return _setup_out(settings, users, database, p.username)


@router.post("/system/setup", response_model=sc.SetupOut)
def setup_finish(body: sc.TutorialIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                 users: UserStore = Depends(get_users), database: Session = Depends(db.get_db)):
    _admin(p)
    onboarding.finish(settings, p.username, body.done)
    if body.done:
        audit.record("system.setup", "system", None, {"llm": settings.llm_provider}, actor=p.username)
    return _setup_out(settings, users, database, p.username)


def _backups_out(request: Request, settings: Settings) -> sc.BackupListOut:
    runner = getattr(request.app.state, "auto_backup", None)
    files = maintenance.auto_backups(settings)
    items = [sc.BackupFileOut(name=f.name, bytes=f.stat().st_size,
                              created_at=datetime.fromtimestamp(f.stat().st_mtime, UTC).replace(tzinfo=None)) for f in files]
    return sc.BackupListOut(every_hours=settings.backup_hours, keep=settings.backup_keep, folder=str(settings.backups_dir),
                            last_at=items[0].created_at if items else None, next_at=runner.next_at() if runner else None,
                            last_error=runner.last_error if runner else None, items=items)


@router.get("/system/backups", response_model=sc.BackupListOut)
def list_backups(request: Request, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    return _backups_out(request, settings)


@router.post("/system/backups", response_model=sc.BackupListOut, status_code=201)
def run_backup(request: Request, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    runner = getattr(request.app.state, "auto_backup", None) or maintenance.AutoBackup(settings)
    try:
        target = runner.run_once()
    except Exception as e:
        raise ApiError(500, "BACKUP_FAILED", f"Não foi possível gravar o backup: {e}")
    audit.record("system.auto_backup", "system", target.name, {"bytes": target.stat().st_size, "origem": "tela"},
                 actor=p.username)
    return _backups_out(request, settings)


@router.get("/system/backups/{name}")
def download_auto_backup(name: str, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    found = next((f for f in maintenance.auto_backups(settings) if f.name == name), None)
    if found is None:
        raise ApiError(404, "NOT_FOUND", "Backup não encontrado.")
    audit.record("system.backup", "system", name, {"bytes": found.stat().st_size, "origem": "automático"}, actor=p.username)
    return FileResponse(found, media_type="application/zip", filename=found.name)


@router.get("/system/diagnostics", response_model=sc.DiagnosticsOut)
def diagnostics(deep: bool = Query(False), p: Principal = Depends(current_user), settings: Settings = Depends(get_settings),
                users: UserStore = Depends(get_users)):
    _admin(p)
    return maintenance.diagnose(settings, users, deep=deep)


@router.post("/system/maintenance", response_model=sc.MaintenanceOut)
def run_maintenance(body: sc.MaintenanceIn, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    try:
        result = maintenance.run(body.action, settings, body.days)
    except maintenance.MaintenanceError as e:
        raise ApiError(400, "MAINTENANCE", str(e), {"days": str(e)} if body.action == "purge_conversations" else None)
    audit.record("maintenance.run", "system", body.action, {"message": result["message"]}, actor=p.username)
    return result


@router.get("/system/backup")
def backup(background: BackgroundTasks, p: Principal = Depends(current_user), settings: Settings = Depends(get_settings)):
    _admin(p)
    folder = Path(tempfile.mkdtemp(prefix="nexo-backup-"))
    name = f"nexo-backup-{datetime.now().strftime('%Y-%m-%d-%H%M')}.zip"
    target = folder / name
    manifest = maintenance.create_backup(settings, target)
    audit.record("system.backup", "system", None, {"bytes": manifest["bytes"], "documentos": manifest["documentos"]},
                 actor=p.username)

    def cleanup() -> None:
        target.unlink(missing_ok=True)
        folder.rmdir()

    background.add_task(cleanup)
    return FileResponse(target, media_type="application/zip", filename=name)


def _audit_query(actor: str, action: str, since: int):
    query = select(db.AuditRow)
    if actor.strip():
        query = query.where(db.AuditRow.actor == actor.strip().lower())
    if action.strip():
        query = query.where(db.AuditRow.action.like(f"{action.strip()}%"))
    if since:
        query = query.where(db.AuditRow.created_at >= db.utcnow() - timedelta(days=since))
    return query


@router.get("/audit", response_model=sc.AuditPage)
def audit_log(actor: str = Query("", max_length=32), action: str = Query("", max_length=40),
              days: int = Query(0, ge=0, le=3650), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
              p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    query = _audit_query(actor, action, days)
    total = database.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = database.scalars(query.order_by(db.AuditRow.created_at.desc(), db.AuditRow.id.desc())
                            .offset(offset).limit(limit)).all()
    items = [sc.AuditItem(id=r.id, created_at=r.created_at, actor=r.actor, action=r.action, label=audit.label(r.action),
                          target_type=r.target_type, target_id=r.target_id, detail=r.detail, ip=r.ip) for r in rows]
    return sc.AuditPage(total=int(total), items=items, actions=audit.ACTIONS)


@router.get("/audit/export")
def audit_export(actor: str = Query("", max_length=32), action: str = Query("", max_length=40),
                 days: int = Query(0, ge=0, le=3650), p: Principal = Depends(current_user),
                 database: Session = Depends(db.get_db)):
    _admin(p)
    rows = database.scalars(_audit_query(actor, action, days).order_by(db.AuditRow.created_at, db.AuditRow.id)).all()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["data_utc", "conta", "acao", "descricao", "tipo", "alvo", "detalhes", "ip"])
    for r in rows:
        writer.writerow([r.created_at.strftime("%Y-%m-%d %H:%M:%S"), r.actor, r.action, audit.label(r.action),
                         r.target_type or "", r.target_id or "", r.detail or "", r.ip or ""])
    name = f"nexo-atividades-{db.utcnow().date().isoformat()}.csv"
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _line(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        inside = ",".join(f'{k}="{str(v).replace(chr(34), chr(39))}"' for k, v in labels.items())
        return f"{name}{{{inside}}} {value}"
    return f"{name} {value}"


@router.get("/health/metrics", include_in_schema=True)
def prometheus(request: Request, p: Principal = Depends(current_user), database: Session = Depends(db.get_db)):
    _admin(p)
    stats = getattr(request.app.state, "stats", None)
    lines = ["# HELP nexo_info Versão do Nexo.", "# TYPE nexo_info gauge", _line("nexo_info", 1, {"version": __version__})]
    if stats is not None:
        lines += ["# HELP nexo_uptime_seconds Tempo desde que o servidor subiu.", "# TYPE nexo_uptime_seconds gauge",
                  _line("nexo_uptime_seconds", round(time.time() - stats.started, 1)),
                  "# HELP nexo_http_requests_total Requisições HTTP atendidas.", "# TYPE nexo_http_requests_total counter"]
        for key, count in sorted(stats.requests.items()):
            lines.append(_line("nexo_http_requests_total", count, {"status": key}))
        lines += ["# HELP nexo_http_request_duration_ms_sum Soma do tempo das requisições.",
                  "# TYPE nexo_http_request_duration_ms_sum counter",
                  _line("nexo_http_request_duration_ms_sum", round(stats.duration_ms, 1)),
                  "# TYPE nexo_http_request_duration_ms_count counter",
                  _line("nexo_http_request_duration_ms_count", sum(stats.requests.values()))]
    lines += ["# HELP nexo_documents Documentos por situação.", "# TYPE nexo_documents gauge"]
    for status, count in database.execute(select(db.DocumentRow.status, func.count()).group_by(db.DocumentRow.status)).all():
        lines.append(_line("nexo_documents", count, {"status": status}))
    chunks = database.scalar(select(func.coalesce(func.sum(db.DocumentRow.chunks), 0))
                             .where(db.DocumentRow.status == "READY")) or 0
    lines += ["# TYPE nexo_chunks gauge", _line("nexo_chunks", int(chunks))]
    answers = database.execute(select(db.MessageRow.answered, func.count()).where(db.MessageRow.role == "assistant")
                               .group_by(db.MessageRow.answered)).all()
    lines += ["# HELP nexo_answers_total Respostas gravadas, respondidas ou não.", "# TYPE nexo_answers_total counter"]
    for answered, count in answers:
        lines.append(_line("nexo_answers_total", count, {"answered": "true" if answered else "false"}))
    latency = database.execute(select(func.coalesce(func.sum(db.MessageRow.latency_ms), 0), func.count())
                               .where(db.MessageRow.role == "assistant", db.MessageRow.latency_ms.is_not(None))).one()
    lines += ["# TYPE nexo_answer_latency_ms_sum counter", _line("nexo_answer_latency_ms_sum", int(latency[0] or 0)),
              "# TYPE nexo_answer_latency_ms_count counter", _line("nexo_answer_latency_ms_count", int(latency[1] or 0))]
    counts = {
        "nexo_conversations": select(func.count()).select_from(db.ConversationRow),
        "nexo_bots": select(func.count()).select_from(db.BotRow),
        "nexo_bases": select(func.count()).select_from(db.KnowledgeBaseRow),
        "nexo_whatsapp_contacts": select(func.count()).select_from(db.WhatsAppContactRow),
        "nexo_whatsapp_waiting": select(func.count()).select_from(db.WhatsAppContactRow)
        .where(db.WhatsAppContactRow.needs_human.is_(True)),
    }
    for name, query in counts.items():
        lines += [f"# TYPE {name} gauge", _line(name, int(database.scalar(query) or 0))]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")
