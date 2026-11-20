from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import db
from nexo.config import Settings

log = logging.getLogger("nexo.onboarding")


def _read(settings: Settings) -> dict:
    path = settings.setup_file
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Ignorando %s: %s", path, e)
        return {}


def _write(settings: Settings, data: dict) -> None:
    path = settings.setup_file
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".instalacao-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def done_at(settings: Settings) -> str | None:
    value = _read(settings).get("concluido_em")
    return value if isinstance(value, str) else None


def finish(settings: Settings, who: str, done: bool = True) -> str | None:
    data = _read(settings)
    if done:
        data.update({"versao": 1, "concluido_em": datetime.now(UTC).replace(microsecond=0).isoformat(), "por": who})
    else:
        data.pop("concluido_em", None)
        data["reaberto_por"] = who
    _write(settings, data)
    return data.get("concluido_em")


def _count(s: Session, query) -> int:
    return int(s.scalar(query) or 0)


def steps(settings: Settings, users, s: Session) -> list[dict]:
    ready = _count(s, select(func.count()).select_from(db.DocumentRow).where(db.DocumentRow.status == "READY"))
    bots = _count(s, select(func.count()).select_from(db.BotRow))
    answered = _count(s, select(func.count()).select_from(db.MessageRow)
                      .where(db.MessageRow.role == "assistant", db.MessageRow.answered.is_(True)))
    widget_questions = _count(s, select(func.coalesce(func.sum(db.WidgetRow.questions), 0)))
    channels = _count(s, select(func.count()).select_from(db.WhatsAppChannelRow)
                      .where(db.WhatsAppChannelRow.provider != "simulador"))
    widgets = _count(s, select(func.count()).select_from(db.WidgetRow))
    keys = _count(s, select(func.count()).select_from(db.ApiKeyRow))
    has_backup = bool(settings.backup_hours) or _count(
        s, select(func.count()).select_from(db.AuditRow).where(db.AuditRow.action == "system.backup")) > 0
    ai = settings.llm_provider != "extrativo"
    model = {"ollama": f"Ollama com {settings.llm_model}", "openai": f"OpenAI com {settings.llm_model}",
             "compativel": f"{settings.llm_model} num serviço compatível"}.get(settings.llm_provider, "Sem modelo de linguagem")
    out = [
        {"id": "password", "label": "Trocar a senha padrão", "done": not users.default_admin_active(), "to": "/configurar",
         "detail": "A conta admin não usa mais a senha pré-definida." if not users.default_admin_active()
         else "A conta admin ainda usa Nexo@2026."},
        {"id": "ai", "label": "Escolher a inteligência", "done": ai, "to": "/sistema?aba=ajustes",
         "detail": model + "." if ai else "Respostas só com frases dos trechos, sem modelo."},
        {"id": "content", "label": "Colocar conteúdo numa base", "done": ready > 0, "to": "/bases",
         "detail": f"{ready} item(ns) pronto(s) para consulta." if ready
         else "Envie arquivos, escreva textos ou crie a base de teste."},
        {"id": "agent", "label": "Criar um agente", "done": bots > 0, "to": "/agentes",
         "detail": f"{bots} agente(s) criado(s)." if bots else "Dê nome, instruções e uma base ao agente."},
        {"id": "question", "label": "Fazer a primeira pergunta", "done": answered + widget_questions > 0, "to": "/chats",
         "detail": "O Nexo já respondeu com base nos documentos." if answered + widget_questions
         else "Converse com o agente em Chats com agentes."},
        {"id": "channel", "label": "Levar o agente ao público", "done": channels + widgets + keys > 0, "to": "/integracoes",
         "detail": "Widget, WhatsApp ou chave de API configurados." if channels + widgets + keys
         else "Publique o widget num site, conecte o WhatsApp ou crie uma chave de API."},
        {"id": "backup", "label": "Proteger com backup", "done": has_backup, "to": "/sistema?aba=manutencao",
         "detail": f"Backup automático a cada {settings.backup_hours} h." if settings.backup_hours
         else ("Backup baixado pela tela." if has_backup else "Ligue o backup automático em Ajustes.")},
    ]
    return out
