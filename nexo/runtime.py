from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from nexo.config import Settings

log = logging.getLogger("nexo.runtime")
_lock = threading.RLock()


@dataclass(frozen=True)
class Adjustable:
    name: str
    group: str
    label: str
    hint: str
    kind: str
    reindex: bool = False
    choices: tuple[str, ...] = ()


ADJUSTABLE: tuple[Adjustable, ...] = (
    Adjustable("llm_model", "Modelo", "Modelo de linguagem",
               "Nome do modelo no provedor configurado, ex.: llama3.1 ou gpt-4o-mini.", "text"),
    Adjustable("llm_temperature", "Modelo", "Temperatura",
               "De 0 a 1. Valores baixos deixam a resposta mais fiel aos trechos.", "float"),
    Adjustable("llm_timeout", "Modelo", "Tempo limite do modelo", "Segundos de espera por resposta do modelo.", "float"),
    Adjustable("verify_answers", "Modelo", "Verificação de fidelidade",
               "Faz uma segunda chamada ao modelo para conferir a resposta.", "bool"),
    Adjustable("top_k", "Busca", "Candidatos da busca", "Quantos trechos a busca vetorial traz antes do reranking.", "int"),
    Adjustable("top_n", "Busca", "Trechos enviados ao modelo",
               "Quantos trechos seguem para a resposta depois do reranking.", "int"),
    Adjustable("min_similarity", "Busca", "Similaridade mínima", "Corte da busca vetorial, de -1 a 1.", "float"),
    Adjustable("min_rerank_score", "Busca", "Nota mínima do reranker", "Corte depois do reranking, de 0 a 1.", "float"),
    Adjustable("history_turns", "Busca", "Turnos de histórico",
               "Quantas trocas anteriores entram na reescrita da pergunta.", "int"),
    Adjustable("chunk_size", "Indexação", "Tamanho do trecho", "Em tokens. Mudar exige reindexar o acervo.", "int",
               reindex=True),
    Adjustable("chunk_overlap", "Indexação", "Sobreposição dos trechos",
               "Em tokens, menor que o tamanho do trecho. Mudar exige reindexar.", "int", reindex=True),
    Adjustable("max_upload_mb", "Indexação", "Tamanho máximo do arquivo", "Em MB, vale para envios e links.", "int"),
    Adjustable("allow_registration", "Acesso", "Cadastro aberto",
               "Qualquer pessoa pode criar a própria conta na tela de entrada.", "bool"),
    Adjustable("token_hours", "Acesso", "Duração da sessão", "Horas até a sessão expirar.", "int"),
    Adjustable("rate_limit", "Acesso", "Limite de perguntas por minuto", "Por conta. Zero desliga o limite.", "int"),
    Adjustable("retention_days", "Manutenção", "Guardar conversas por",
               "Dias. Conversas não fixadas mais antigas são apagadas. Zero guarda para sempre.", "int"),
    Adjustable("whatsapp_history", "WhatsApp", "Histórico do contato", "Mensagens anteriores que o agente lê no WhatsApp.", "int"),
)

BY_NAME = {a.name: a for a in ADJUSTABLE}


class AdjustError(ValueError):
    def __init__(self, fields: dict[str, str]):
        super().__init__("; ".join(fields.values()))
        self.fields = fields


def _read(settings: Settings) -> dict[str, Any]:
    path = settings.overrides_file
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Ignorando %s: %s", path, e)
        return {}
    values = data.get("valores", {}) if isinstance(data, dict) else {}
    return {k: v for k, v in values.items() if k in BY_NAME}


def _write(settings: Settings, values: dict[str, Any], who: str | None) -> None:
    path = settings.overrides_file
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"versao": 1, "alterado_por": who, "valores": values}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ajustes-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def baseline() -> Settings:
    return Settings()


def overrides(settings: Settings) -> dict[str, Any]:
    with _lock:
        return _read(settings)


def apply(settings: Settings) -> list[str]:
    applied: list[str] = []
    with _lock:
        for name, value in _read(settings).items():
            try:
                setattr(settings, name, value)
                applied.append(name)
            except ValidationError as e:
                log.warning("Ajuste %s ignorado: %s", name, e.errors()[0].get("msg"))
    return applied


def _messages(e: ValidationError, name: str) -> str:
    err = e.errors()[0]
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if "greater_than_equal" in kind:
        return f"Use um valor a partir de {ctx.get('ge')}."
    if "less_than_equal" in kind:
        return f"Use um valor até {ctx.get('le')}."
    if "greater_than" in kind:
        return f"Use um valor maior que {ctx.get('gt')}."
    if kind.startswith("int") or kind.startswith("float"):
        return "Informe um número."
    if kind.startswith("bool"):
        return "Escolha sim ou não."
    return "Valor inválido."


def update(settings: Settings, changes: dict[str, Any], who: str | None) -> list[str]:
    unknown = [k for k in changes if k not in BY_NAME]
    if unknown:
        raise AdjustError({k: "Este item não pode ser ajustado pela tela." for k in unknown})
    with _lock:
        stored = _read(settings)
        trial = settings.model_copy()
        fields: dict[str, str] = {}
        for name, value in changes.items():
            if isinstance(value, str) and BY_NAME[name].kind == "text":
                value = value.strip()
                if not value:
                    fields[name] = "Preencha este campo."
                    continue
            try:
                setattr(trial, name, value)
            except ValidationError as e:
                fields[name] = _messages(e, name)
        if not fields and trial.chunk_overlap >= trial.chunk_size:
            fields["chunk_overlap"] = "A sobreposição precisa ser menor que o tamanho do trecho."
        if not fields and trial.top_n > trial.top_k:
            fields["top_n"] = "Envie ao modelo no máximo a quantidade de candidatos da busca."
        if fields:
            raise AdjustError(fields)
        base = baseline()
        changed: list[str] = []
        for name in changes:
            value = getattr(trial, name)
            if getattr(settings, name) != value:
                changed.append(name)
            setattr(settings, name, value)
            if getattr(base, name) == value:
                stored.pop(name, None)
            else:
                stored[name] = value
        _write(settings, stored, who)
    return changed


def reset(settings: Settings, who: str | None, names: list[str] | None = None) -> list[str]:
    with _lock:
        stored = _read(settings)
        base = baseline()
        targets = names or list(stored)
        changed: list[str] = []
        for name in targets:
            if name not in BY_NAME:
                continue
            value = getattr(base, name)
            if getattr(settings, name) != value:
                changed.append(name)
            setattr(settings, name, value)
            stored.pop(name, None)
        _write(settings, stored, who)
    return changed


def describe(settings: Settings) -> list[dict[str, Any]]:
    stored = overrides(settings)
    base = baseline()
    out = []
    fields = Settings.model_fields
    for a in ADJUSTABLE:
        meta = {m.__class__.__name__: m for m in fields[a.name].metadata}
        limits = {}
        for key in ("ge", "le", "gt", "lt"):
            for m in meta.values():
                if hasattr(m, key) and getattr(m, key) is not None:
                    limits[key] = getattr(m, key)
        out.append({"name": a.name, "group": a.group, "label": a.label, "hint": a.hint, "kind": a.kind,
                    "value": getattr(settings, a.name), "default": getattr(base, a.name), "overridden": a.name in stored,
                    "reindex": a.reindex, "min": limits.get("ge", limits.get("gt")), "max": limits.get("le", limits.get("lt"))})
    return out
