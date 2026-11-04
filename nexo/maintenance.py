from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from sqlalchemy import func, select, text

from nexo import __version__, db, jobs
from nexo.config import Settings
from nexo.rag import providers
from nexo.rag.engine import get_engine

log = logging.getLogger("nexo.maintenance")

ACTIONS = ("reindex_failed", "reindex_outdated", "reindex_all", "clean_orphans", "purge_conversations", "vacuum")
BACKUP_FILES = ("usuarios.json", "ajustes.json", ".segredo")


class MaintenanceError(RuntimeError):
    pass


@dataclass
class Check:
    id: str
    group: str
    label: str
    status: str
    detail: str
    hint: str | None = None


def _size(value: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{value} B"


def _count(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _sqlite_path(settings: Settings) -> Path | None:
    url = settings.sqlalchemy_url
    if not url.startswith("sqlite:///"):
        return None
    return Path(url[len("sqlite:///"):])


def document_files(s) -> tuple[list[db.DocumentRow], list[db.DocumentRow]]:
    rows = s.scalars(select(db.DocumentRow).where(db.DocumentRow.kind != "note")).all()
    missing = [r for r in rows if not jobs.stored_file(r).exists()]
    return list(rows), missing


def orphan_files(settings: Settings, s) -> list[Path]:
    known = set(s.scalars(select(db.DocumentRow.id)).all())
    if not settings.uploads_dir.exists():
        return []
    return [f for f in settings.uploads_dir.iterdir() if f.is_file() and f.stem not in known]


def outdated_ids(s, signature: str) -> list[str]:
    return list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status == "READY",
                                                         db.DocumentRow.index_signature.is_not(None),
                                                         db.DocumentRow.index_signature != signature)))


def _ollama_models(settings: Settings) -> tuple[list[str] | None, str | None]:
    request = urllib.request.Request(settings.ollama_url.rstrip("/") + "/api/tags", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read() or b"{}")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        reason = getattr(e, "reason", e)
        return None, f"Não foi possível falar com o Ollama em {settings.ollama_url}: {reason}"
    return [str(m.get("name") or m.get("model") or "") for m in data.get("models") or []], None


def _has_model(names: list[str], wanted: str) -> bool:
    wanted = wanted.strip()
    return any(n == wanted or n == f"{wanted}:latest" or n.split(":")[0] == wanted for n in names)


def _last_backup(s) -> datetime | None:
    return s.scalar(select(func.max(db.AuditRow.created_at)).where(db.AuditRow.action == "system.backup"))


def diagnose(settings: Settings, users, deep: bool = False) -> dict:
    checks: list[Check] = []
    add = checks.append
    engine = get_engine(settings)
    started = time.perf_counter()
    try:
        with db.session() as s:
            s.execute(select(1))
        ms = int((time.perf_counter() - started) * 1000)
        dialect = "SQLite" if settings.sqlalchemy_url.startswith("sqlite") else settings.sqlalchemy_url.split(":")[0]
        path = _sqlite_path(settings)
        extra = ""
        if path and path.exists():
            total = sum(f.stat().st_size for f in (path, path.with_name(path.name + "-wal")) if f.exists())
            extra = f", {_size(total)} em disco"
        add(Check("database", "Servidor", "Banco relacional", "ok", f"{dialect} respondeu em {ms} ms{extra}."))
    except Exception as e:
        add(Check("database", "Servidor", "Banco relacional", "fail", f"O banco não respondeu: {e}",
                  "Confira NEXO_DATABASE_URL e se o servidor do banco está no ar."))
        return _summary(checks, deep)

    usage = shutil.disk_usage(settings.data_dir)
    free = usage.free
    status = "fail" if free < 200 * 1024 ** 2 else "warn" if free < 1024 ** 3 else "ok"
    add(Check("disk", "Servidor", "Espaço em disco", status, f"{_size(free)} livres no disco da pasta de dados.",
              None if status == "ok" else "Libere espaço: o banco vetorial e os envios precisam de folga para crescer."))

    if users.default_admin_active():
        add(Check("default_admin", "Segurança", "Senha padrão do administrador", "fail",
                  "A conta admin ainda usa a senha pré-definida Nexo@2026.", "Troque a senha em Sistema e conta > Visão geral."))
    else:
        add(Check("default_admin", "Segurança", "Senha padrão do administrador", "ok", "A senha pré-definida não está mais em uso."))
    if settings.secret and len(settings.secret) < 32:
        add(Check("secret", "Segurança", "Chave das sessões", "warn", "NEXO_SECRET tem menos de 32 caracteres.",
                  "Use um valor longo e aleatório ou deixe vazio para o Nexo gerar um em data/.segredo."))
    else:
        add(Check("secret", "Segurança", "Chave das sessões", "ok",
                  "Definida em NEXO_SECRET." if settings.secret else "Gerada e guardada em data/.segredo."))
    if settings.rate_limit:
        add(Check("rate_limit", "Segurança", "Limite de perguntas", "ok", f"{settings.rate_limit} perguntas por minuto por conta."))
    else:
        add(Check("rate_limit", "Segurança", "Limite de perguntas", "warn", "Sem limite de perguntas por conta.",
                  "Defina um limite em Ajustes para proteger o modelo de abusos e integrações com defeito."))

    if settings.llm_provider == "extrativo":
        add(Check("llm", "Modelos", "Modelo de linguagem", "warn", "Modo extrativo: as respostas são frases dos trechos, sem LLM.",
                  "Configure NEXO_LLM_PROVIDER=ollama ou openai para respostas redigidas."))
    elif settings.llm_provider == "ollama":
        names, error = _ollama_models(settings)
        if error:
            add(Check("llm", "Modelos", "Modelo de linguagem", "fail", error,
                      "Inicie o Ollama (ollama serve) ou confira NEXO_OLLAMA_URL."))
        elif not _has_model(names or [], settings.llm_model):
            add(Check("llm", "Modelos", "Modelo de linguagem", "fail",
                      f"O Ollama está no ar, mas não tem o modelo {settings.llm_model}.", f"Rode: ollama pull {settings.llm_model}"))
        else:
            add(Check("llm", "Modelos", "Modelo de linguagem", "ok", f"Ollama no ar com {settings.llm_model}."))
    else:
        if not settings.openai_api_key and not settings.openai_base_url:
            add(Check("llm", "Modelos", "Modelo de linguagem", "fail", "OPENAI_API_KEY não está definida.",
                      "Coloque a chave no .env e reinicie o servidor."))
        else:
            later = "" if deep else " A conexão é testada no diagnóstico completo."
            add(Check("llm", "Modelos", "Modelo de linguagem", "ok" if deep else "info",
                      f"OpenAI configurada com {settings.llm_model}.{later}"))
    if deep and settings.llm_provider != "extrativo" and checks[-1].status != "fail":
        try:
            t0 = time.perf_counter()
            reply = engine.llm().complete("Responda apenas com a palavra ok.").text.strip()
            ms = int((time.perf_counter() - t0) * 1000)
            add(Check("llm_call", "Modelos", "Chamada de teste ao modelo", "ok", f"Respondeu em {ms} ms: “{reply[:40]}”."))
        except Exception as e:
            add(Check("llm_call", "Modelos", "Chamada de teste ao modelo", "fail", f"O modelo não respondeu: {e}"))

    if settings.embed_provider == "hash":
        add(Check("embedding", "Modelos", "Embeddings", "warn", "Embedding léxico de teste: a busca não entende sinônimos.",
                  "Use NEXO_EMBED_PROVIDER=huggingface para uso real."))
    elif settings.embed_provider == "ollama" and settings.llm_provider != "ollama":
        names, error = _ollama_models(settings)
        ok = not error and _has_model(names or [], settings.embed_model)
        add(Check("embedding", "Modelos", "Embeddings", "ok" if ok else "fail",
                  f"Ollama com {settings.embed_model}." if ok else (error or f"Falta o modelo {settings.embed_model} no Ollama."),
                  None if ok else f"Rode: ollama pull {settings.embed_model}"))
    else:
        add(Check("embedding", "Modelos", "Embeddings", "ok" if engine.loaded else "info",
                  f"{settings.embed_provider} · {settings.embed_model}" + ("" if engine.loaded else ", carrega na primeira busca.")))
    if deep:
        try:
            t0 = time.perf_counter()
            engine._ensure_index()
            engine._embed.get_query_embedding("teste de diagnóstico")
            add(Check("embedding_call", "Modelos", "Cálculo de embedding", "ok",
                      f"Vetor calculado em {int((time.perf_counter() - t0) * 1000)} ms."))
        except Exception as e:
            add(Check("embedding_call", "Modelos", "Cálculo de embedding", "fail", f"Não foi possível calcular: {e}"))

    if settings.reranker == "none":
        add(Check("reranker", "Modelos", "Reranking", "warn", "Desligado: a ordem dos trechos vem só da busca vetorial.",
                  "Ligue NEXO_RERANKER=huggingface para respostas mais precisas."))
    elif settings.reranker == "cohere" and not settings.cohere_api_key:
        add(Check("reranker", "Modelos", "Reranking", "fail", "COHERE_API_KEY não está definida."))
    elif deep:
        try:
            engine.reranker()
            add(Check("reranker", "Modelos", "Reranking", "ok", f"{settings.reranker} carregado."))
        except Exception as e:
            add(Check("reranker", "Modelos", "Reranking", "fail", f"Não foi possível carregar: {e}"))
    else:
        add(Check("reranker", "Modelos", "Reranking", "info", f"{settings.reranker} configurado."))

    with db.session() as s:
        rows, missing = document_files(s)
        orphans = orphan_files(settings, s)
        counts = dict(s.execute(select(db.DocumentRow.status, func.count()).group_by(db.DocumentRow.status)).all())
        expected = int(s.scalar(select(func.coalesce(func.sum(db.DocumentRow.chunks), 0))
                                .where(db.DocumentRow.status == "READY")) or 0)
        outdated = outdated_ids(s, providers.index_signature(settings))
        channels = s.scalars(select(db.WhatsAppChannelRow)).all()
        hooks = s.scalars(select(db.WebhookRow).where(db.WebhookRow.active.is_(True))).all()
        last_backup = _last_backup(s)

    if engine.loaded or deep:
        found = engine.count()
        if found is None:
            add(Check("vectors", "Acervo", "Banco vetorial", "fail", "Não foi possível contar os trechos do banco vetorial."))
        elif found != expected:
            add(Check("vectors", "Acervo", "Banco vetorial", "warn",
                      f"{_count(found)} trechos no banco vetorial e {_count(expected)} esperados pelos documentos prontos.",
                      "Rode Limpar órfãos e depois Reindexar desatualizados ou tudo."))
        else:
            add(Check("vectors", "Acervo", "Banco vetorial", "ok", f"{_count(found)} trechos, iguais aos esperados."))
    else:
        add(Check("vectors", "Acervo", "Banco vetorial", "info",
                  "Abre na primeira busca. Rode o diagnóstico completo para contar os trechos."))

    if missing:
        add(Check("files", "Acervo", "Arquivos originais", "fail", f"{len(missing)} documento(s) sem o arquivo na pasta de uploads.",
                  "Restaure a pasta data/uploads de um backup ou envie os arquivos de novo."))
    else:
        add(Check("files", "Acervo", "Arquivos originais", "ok", f"{len(rows)} arquivo(s) no lugar."))
    if orphans:
        total = sum(f.stat().st_size for f in orphans)
        add(Check("orphans", "Acervo", "Arquivos sem documento", "warn", f"{len(orphans)} arquivo(s) sobrando, {_size(total)}.",
                  "Rode Limpar órfãos em Manutenção."))
    else:
        add(Check("orphans", "Acervo", "Arquivos sem documento", "ok", "Nenhum arquivo sobrando."))
    failed = int(counts.get("FAILED", 0))
    add(Check("failed", "Acervo", "Documentos com falha", "warn" if failed else "ok",
              f"{failed} documento(s) com falha na indexação." if failed else "Nenhum.",
              "Veja o erro em Documentos e use Reindexar falhas." if failed else None))
    add(Check("outdated", "Acervo", "Índice desatualizado", "warn" if outdated else "ok",
              f"{len(outdated)} documento(s) indexado(s) com outra configuração de embeddings ou trechos." if outdated
              else "Todos os documentos usam a configuração atual.",
              "Rode Reindexar desatualizados em Manutenção." if outdated else None))
    queue = int(counts.get("PENDING", 0)) + int(counts.get("PROCESSING", 0))
    add(Check("queue", "Acervo", "Fila de indexação", "info" if queue else "ok",
              f"{queue} documento(s) na fila." if queue else "Fila vazia."))

    remote = [c for c in channels if c.provider in ("cloud", "evolution")]
    if remote and not settings.public_url:
        add(Check("public_url", "Integrações", "Endereço público", "warn",
                  "Há conexões do WhatsApp, mas NEXO_PUBLIC_URL está vazio.",
                  "Defina o endereço público para o WhatsApp alcançar o webhook do Nexo."))
    broken = [c.name for c in channels if c.last_error]
    if channels:
        add(Check("whatsapp", "Integrações", "Conexões do WhatsApp", "warn" if broken else "ok",
                  f"Último erro em: {', '.join(broken)}." if broken else f"{len(channels)} conexão(ões) sem erro registrado."))
    failing = [h.url for h in hooks if h.last_error]
    if hooks:
        add(Check("webhooks", "Integrações", "Webhooks", "warn" if failing else "ok",
                  f"{len(failing)} webhook(s) com a última entrega falhando." if failing else f"{len(hooks)} webhook(s) entregando."))
    if settings.cors_list:
        add(Check("cors", "Integrações", "CORS", "info", "Origens liberadas: " + ", ".join(settings.cors_list)))

    if last_backup is None:
        add(Check("backup", "Manutenção", "Backup", "warn", "Nenhum backup baixado pela tela ainda.",
                  "Baixe um backup em Manutenção ou rode python -m nexo backup."))
    else:
        age = db.utcnow() - last_backup
        add(Check("backup", "Manutenção", "Backup", "warn" if age > timedelta(days=30) else "ok",
                  f"Último backup baixado em {last_backup.strftime('%d/%m/%Y %H:%M')} (UTC)."))
    add(Check("retention", "Manutenção", "Retenção de conversas", "info",
              f"Conversas não fixadas com mais de {settings.retention_days} dias são apagadas." if settings.retention_days
              else "As conversas ficam guardadas para sempre."))
    return _summary(checks, deep)


def _summary(checks: list[Check], deep: bool) -> dict:
    tally = {k: sum(1 for c in checks if c.status == k) for k in ("ok", "warn", "fail", "info")}
    return {"checked_at": db.utcnow(), "deep": deep, **tally, "checks": [asdict(c) for c in checks]}


def run(action: str, settings: Settings, days: int | None = None) -> dict:
    if action not in ACTIONS:
        raise MaintenanceError("Ação de manutenção desconhecida.")
    signature = providers.index_signature(settings)
    if action in ("reindex_failed", "reindex_outdated", "reindex_all"):
        with db.session() as s:
            if action == "reindex_failed":
                ids = list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status == "FAILED")))
            elif action == "reindex_outdated":
                ids = outdated_ids(s, signature)
            else:
                ids = list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status.in_(["READY", "FAILED"]))))
        queued = jobs.requeue(ids)
        skipped = len(ids) - queued
        message = f"{queued} documento(s) na fila de indexação."
        if skipped:
            message += f" {skipped} sem o arquivo original ficaram de fora."
        return {"action": action, "message": message, "count": queued, "skipped": skipped}
    if action == "clean_orphans":
        engine = get_engine(settings)
        with db.session() as s:
            files = orphan_files(settings, s)
            known = set(s.scalars(select(db.DocumentRow.id)).all())
        freed = 0
        for f in files:
            freed += f.stat().st_size
            f.unlink(missing_ok=True)
        stray = [k for k in engine.source_ids() if k not in known]
        for source in stray:
            if source:
                engine.delete(source)
        message = f"{len(files)} arquivo(s) removido(s), {_size(freed)} liberados, e vetores de {len(stray)} documento(s) apagado(s)."
        return {"action": action, "message": message, "count": len(files) + len(stray), "skipped": 0}
    if action == "purge_conversations":
        days = int(days or settings.retention_days or 0)
        if days < 1:
            raise MaintenanceError("Informe a partir de quantos dias as conversas devem ser apagadas.")
        removed = purge_conversations(days)
        return {"action": action, "message": f"{removed} conversa(s) com mais de {days} dias apagada(s).", "count": removed,
                "skipped": 0}
    path = _sqlite_path(settings)
    if path is None:
        raise MaintenanceError("Compactar só vale para o SQLite. Use a ferramenta do seu banco.")

    def footprint() -> int:
        return sum(f.stat().st_size for f in (path, path.with_name(path.name + "-wal")) if f.exists())

    before = footprint()
    with db.engine().connect() as conn:
        auto = conn.execution_options(isolation_level="AUTOCOMMIT")
        auto.execute(text("VACUUM"))
        auto.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    after = footprint()
    return {"action": action, "message": f"Banco compactado de {_size(before)} para {_size(after)}.", "count": 1, "skipped": 0}


def purge_conversations(days: int) -> int:
    cutoff = db.utcnow() - timedelta(days=days)
    with db.session() as s:
        rows = s.scalars(select(db.ConversationRow).where(db.ConversationRow.updated_at < cutoff,
                                                          db.ConversationRow.pinned.is_(False))).all()
        for row in rows:
            s.delete(row)
        s.commit()
        return len(rows)


class Retention:
    def __init__(self, settings: Settings, every: float = 6 * 3600):
        self.settings = settings
        self.every = every
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="nexo-retencao", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            days = self.settings.retention_days
            if days:
                try:
                    removed = purge_conversations(days)
                    if removed:
                        log.info("Retenção: %d conversa(s) com mais de %d dias apagada(s).", removed, days)
                except Exception:
                    log.exception("Falha na retenção de conversas")
            self._stop.wait(self.every)


def create_backup(settings: Settings, dest: Path) -> dict:
    path = _sqlite_path(settings)
    with db.session() as s:
        documents = int(s.scalar(select(func.count()).select_from(db.DocumentRow)) or 0)
    files = [f for f in settings.uploads_dir.iterdir() if f.is_file()] if settings.uploads_dir.exists() else []
    manifest = {"produto": "Nexo", "versao": __version__, "criado_em": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "banco": "sqlite" if path else settings.sqlalchemy_url.split(":")[0], "inclui_banco": bool(path and path.exists()),
                "documentos": documents, "arquivos": len(files)}
    with tempfile.TemporaryDirectory(prefix="nexo-backup-") as temp, \
            zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        if path and path.exists():
            copy = Path(temp) / "nexo.db"
            source = sqlite3.connect(str(path))
            target = sqlite3.connect(str(copy))
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            archive.write(copy, "nexo.db")
        for name in BACKUP_FILES:
            item = settings.data_dir / name
            if item.is_file():
                archive.write(item, name)
        for f in files:
            archive.write(f, f"uploads/{f.name}")
        archive.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    manifest["bytes"] = dest.stat().st_size
    return manifest


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    allowed = {"nexo.db", "manifesto.json", *BACKUP_FILES}
    members = []
    for info in archive.infolist():
        name = PurePosixPath(info.filename)
        if info.is_dir():
            continue
        if name.is_absolute() or ".." in name.parts:
            raise MaintenanceError(f"O backup tem um caminho inválido: {info.filename}")
        if str(name) in allowed or (len(name.parts) == 2 and name.parts[0] == "uploads"):
            members.append(info)
    return members


def restore_backup(archive_path: Path, data_dir: Path, replace: bool = False) -> dict:
    if not archive_path.is_file():
        raise MaintenanceError(f"Arquivo não encontrado: {archive_path}")
    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as e:
        raise MaintenanceError("O arquivo não é um backup .zip do Nexo.") from e
    with archive:
        if "manifesto.json" not in archive.namelist():
            raise MaintenanceError("O arquivo não tem o manifesto do Nexo.")
        manifest = json.loads(archive.read("manifesto.json"))
        members = _safe_members(archive)
        moved = None
        if data_dir.exists() and any(data_dir.iterdir()):
            if not replace:
                raise MaintenanceError(f"A pasta {data_dir} já tem dados. Use --substituir para guardar uma cópia e restaurar.")
            moved = data_dir.with_name(f"{data_dir.name}.antes-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            data_dir.rename(moved)
        data_dir.mkdir(parents=True, exist_ok=True)
        for info in members:
            target = data_dir / PurePosixPath(info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    queued = 0
    database = data_dir / "nexo.db"
    if database.exists():
        conn = sqlite3.connect(str(database))
        try:
            cur = conn.execute("UPDATE nx_document SET status = 'PENDING', error = NULL WHERE status IN ('READY', 'PROCESSING')")
            queued = cur.rowcount
            conn.commit()
        finally:
            conn.close()
    return {"manifest": manifest, "files": len(members), "queued": queued, "previous": str(moved) if moved else None}
