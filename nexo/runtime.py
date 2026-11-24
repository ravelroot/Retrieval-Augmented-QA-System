from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
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
    choices: tuple[tuple[str, str], ...] = ()
    required: bool = True
    wipe: bool = False
    placeholder: str = ""


LLM_CHOICES = (
    ("ollama", "Ollama, no seu computador ou servidor"),
    ("openai", "OpenAI"),
    ("compativel", "Compatível com a OpenAI (Groq, OpenRouter, Gemini…)"),
    ("extrativo", "Sem modelo: só frases dos trechos (testes)"),
)
EMBED_CHOICES = (
    ("huggingface", "HuggingFace, local e gratuito"),
    ("openai", "OpenAI"),
    ("ollama", "Ollama"),
    ("hash", "Léxico, sem modelo (testes)"),
)
RERANK_CHOICES = (
    ("huggingface", "HuggingFace, local e gratuito"),
    ("cohere", "Cohere"),
    ("none", "Desligado"),
)

ADJUSTABLE: tuple[Adjustable, ...] = (
    Adjustable("llm_provider", "Inteligência", "Quem escreve as respostas",
               "Escolha onde o modelo de linguagem roda. Teste a conexão antes de salvar.", "choice", choices=LLM_CHOICES),
    Adjustable("llm_model", "Inteligência", "Modelo de linguagem",
               "Nome do modelo no provedor, ex.: llama3.1, gpt-4o-mini ou o nome listado pelo serviço.", "text"),
    Adjustable("ollama_url", "Inteligência", "Endereço do Ollama", "Onde o Ollama responde. No mesmo computador: http://localhost:11434.",
               "url", placeholder="http://localhost:11434"),
    Adjustable("ollama_keep_alive", "Inteligência", "Manter o modelo do Ollama carregado",
               "Tempo que o modelo fica na memória depois de responder, ex.: 30m ou 2h. Evita recarregar a cada pergunta. "
               "-1 mantém sempre; 0 libera a memória na hora, mas cada resposta volta a carregar o modelo.", "text",
               placeholder="30m"),
    Adjustable("openai_base_url", "Inteligência", "Endereço do serviço compatível",
               "Obrigatório para serviços compatíveis. Vazio usa a própria OpenAI.", "url", required=False,
               placeholder="https://api.groq.com/openai/v1"),
    Adjustable("openai_api_key", "Inteligência", "Chave da API (OpenAI ou compatível)",
               "Fica guardada em data/segredos.json e nunca volta para a tela. Deixe em branco para manter a atual.", "secret",
               required=False),
    Adjustable("embed_provider", "Embeddings", "Quem gera os embeddings",
               "Trocar apaga os vetores e reindexa todo o acervo com o novo modelo.", "choice", reindex=True, wipe=True,
               choices=EMBED_CHOICES),
    Adjustable("embed_model", "Embeddings", "Modelo de embeddings",
               "Ex.: intfloat/multilingual-e5-small, text-embedding-3-small ou nomic-embed-text. Trocar reindexa o acervo.",
               "text", reindex=True, wipe=True),
    Adjustable("reranker", "Reranking", "Reranking",
               "Reordena os trechos pela relação real com a pergunta e descarta os que não ajudam. Desligado, a resposta "
               "sai um pouco mais rápido, com menos precisão.", "choice", choices=RERANK_CHOICES),
    Adjustable("rerank_model", "Reranking", "Modelo de reranking do HuggingFace",
               "Usado quando o reranking é do HuggingFace.", "text"),
    Adjustable("cohere_model", "Reranking", "Modelo de reranking da Cohere", "Usado quando o reranking é da Cohere.", "text"),
    Adjustable("cohere_api_key", "Reranking", "Chave da Cohere",
               "Fica guardada em data/segredos.json e nunca volta para a tela. Deixe em branco para manter a atual.", "secret",
               required=False),
    Adjustable("llm_temperature", "Modelo", "Temperatura",
               "De 0 a 1. Valores baixos deixam a resposta mais fiel aos trechos.", "float"),
    Adjustable("llm_timeout", "Modelo", "Tempo limite do modelo", "Segundos de espera por resposta do modelo.", "float"),
    Adjustable("verify_answers", "Modelo", "Verificação de fidelidade",
               "Faz uma segunda chamada ao modelo para conferir a resposta.", "bool"),
    Adjustable("top_k", "Busca", "Candidatos da busca", "Quantos trechos a busca vetorial traz antes do reranking.", "int"),
    Adjustable("top_n", "Busca", "Trechos enviados ao modelo",
               "Quantos trechos seguem para a resposta depois do reranking.", "int"),
    Adjustable("min_similarity", "Busca", "Similaridade mínima", "Corte da busca vetorial, de -1 a 1.", "float"),
    Adjustable("min_rerank_score", "Busca", "Nota mínima do reranker",
               "De 0 a 1: a chance de o trecho responder à pergunta. Abaixo do corte, o modelo ainda avalia os 2 melhores "
               "trechos se chegarem perto; sem nenhum perto, a resposta é que não encontrou.", "float"),
    Adjustable("history_turns", "Busca", "Turnos de histórico",
               "Quantas trocas anteriores o modelo lê quando a pergunta depende delas, como em “e o plano Plus?”. Zero "
               "trata cada pergunta sozinha.", "int"),
    Adjustable("chunk_size", "Indexação", "Tamanho do trecho", "Em tokens. Mudar exige reindexar o acervo.", "int",
               reindex=True),
    Adjustable("chunk_overlap", "Indexação", "Sobreposição dos trechos",
               "Em tokens, menor que o tamanho do trecho. Mudar exige reindexar.", "int", reindex=True),
    Adjustable("max_upload_mb", "Indexação", "Tamanho máximo do arquivo", "Em MB, vale para envios e links.", "int"),
    Adjustable("public_url", "Acesso", "Endereço público do Nexo",
               "Como a internet chega ao Nexo. Usado no webhook do WhatsApp e no código do widget.", "url", required=False,
               placeholder="https://nexo.suaempresa.com.br"),
    Adjustable("allow_registration", "Acesso", "Cadastro aberto",
               "Qualquer pessoa pode criar a própria conta na tela de entrada.", "bool"),
    Adjustable("token_hours", "Acesso", "Duração da sessão", "Horas até a sessão expirar.", "int"),
    Adjustable("rate_limit", "Acesso", "Limite de perguntas por minuto", "Por conta. Zero desliga o limite.", "int"),
    Adjustable("widget_rate_limit", "Acesso", "Perguntas por minuto no widget",
               "Por visitante, em cada widget publicado em sites.", "int"),
    Adjustable("backup_hours", "Manutenção", "Backup automático a cada",
               "Horas entre um backup e outro, gravados em data/backups. Zero desliga.", "int"),
    Adjustable("backup_keep", "Manutenção", "Backups automáticos guardados",
               "Quantos arquivos ficam na pasta. Os mais antigos são apagados.", "int"),
    Adjustable("retention_days", "Manutenção", "Guardar conversas por",
               "Dias. Conversas não fixadas mais antigas são apagadas. Zero guarda para sempre.", "int"),
    Adjustable("whatsapp_history", "WhatsApp", "Histórico do contato", "Mensagens anteriores que o agente lê no WhatsApp.", "int"),
)

BY_NAME = {a.name: a for a in ADJUSTABLE}
SECRETS = tuple(a.name for a in ADJUSTABLE if a.kind == "secret")
WIPE = tuple(a.name for a in ADJUSTABLE if a.wipe)


class AdjustError(ValueError):
    def __init__(self, fields: dict[str, str]):
        super().__init__("; ".join(fields.values()))
        self.fields = fields


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Ignorando %s: %s", path, e)
        return {}
    values = data.get("valores", {}) if isinstance(data, dict) else {}
    return {k: v for k, v in values.items() if k in BY_NAME}


def _save(path: Path, values: dict[str, Any], who: str | None, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"versao": 1, "alterado_por": who, "valores": values}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if private:
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
    os.replace(tmp, path)


def _read(settings: Settings) -> dict[str, Any]:
    plain = {k: v for k, v in _load(settings.overrides_file).items() if k not in SECRETS}
    secret = {k: v for k, v in _load(settings.secrets_file).items() if k in SECRETS}
    return {**plain, **secret}


def _write(settings: Settings, values: dict[str, Any], who: str | None) -> None:
    _save(settings.overrides_file, {k: v for k, v in values.items() if k not in SECRETS}, who)
    secret = {k: v for k, v in values.items() if k in SECRETS}
    if secret or settings.secrets_file.exists():
        _save(settings.secrets_file, secret, who, private=True)


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


def _messages(e: ValidationError) -> str:
    err = e.errors()[0]
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if "greater_than_equal" in kind:
        return f"Use um valor a partir de {ctx.get('ge')}."
    if "less_than_equal" in kind:
        return f"Use um valor até {ctx.get('le')}."
    if "greater_than" in kind:
        return f"Use um valor maior que {ctx.get('gt')}."
    if kind == "literal_error":
        return "Escolha uma das opções."
    if kind == "value_error":
        return str(ctx.get("error") or err.get("msg", "Valor inválido.")).removeprefix("Value error, ")
    if kind.startswith("int") or kind.startswith("float"):
        return "Informe um número."
    if kind.startswith("bool"):
        return "Escolha sim ou não."
    return "Valor inválido."


def _normalize(item: Adjustable, value: Any) -> tuple[Any, str | None]:
    if item.kind in ("text", "url", "secret", "choice"):
        value = "" if value is None else str(value).strip()
        if not value:
            if item.kind == "secret":
                return None, None
            if item.required:
                return None, "Preencha este campo."
            return None, None
    return value, None


def trial(settings: Settings, changes: dict[str, Any]) -> tuple[Settings, dict[str, str]]:
    unknown = [k for k in changes if k not in BY_NAME]
    if unknown:
        raise AdjustError({k: "Este item não pode ser ajustado pela tela." for k in unknown})
    copy = settings.model_copy()
    fields: dict[str, str] = {}
    for name, raw in changes.items():
        item = BY_NAME[name]
        value, problem = _normalize(item, raw)
        if problem:
            fields[name] = problem
            continue
        if item.kind == "secret" and value is None:
            continue
        try:
            setattr(copy, name, value)
        except ValidationError as e:
            fields[name] = _messages(e)
    if not fields and copy.chunk_overlap >= copy.chunk_size:
        fields["chunk_overlap"] = "A sobreposição precisa ser menor que o tamanho do trecho."
    if not fields and copy.top_n > copy.top_k:
        fields["top_n"] = "Envie ao modelo no máximo a quantidade de candidatos da busca."
    if not fields and copy.llm_provider == "compativel" and not copy.openai_base_url:
        fields["openai_base_url"] = "Informe o endereço do serviço compatível."
    return copy, fields


def update(settings: Settings, changes: dict[str, Any], who: str | None) -> list[str]:
    with _lock:
        stored = _read(settings)
        candidate, fields = trial(settings, changes)
        if fields:
            raise AdjustError(fields)
        base = baseline()
        changed: list[str] = []
        for name in changes:
            if BY_NAME[name].kind == "secret" and not str(changes[name] or "").strip():
                continue
            value = getattr(candidate, name)
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


def _limits(name: str) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    for m in Settings.model_fields[name].metadata:
        for key in ("ge", "le", "gt", "lt"):
            if getattr(m, key, None) is not None:
                limits[key] = getattr(m, key)
    return limits


def describe(settings: Settings) -> list[dict[str, Any]]:
    stored = overrides(settings)
    base = baseline()
    out = []
    for a in ADJUSTABLE:
        limits = _limits(a.name)
        secret = a.kind == "secret"
        value = getattr(settings, a.name)
        default = getattr(base, a.name)
        out.append({"name": a.name, "group": a.group, "label": a.label, "hint": a.hint, "kind": a.kind,
                    "value": "" if secret or value is None else value, "default": "" if secret or default is None else default,
                    "overridden": a.name in stored, "reindex": a.reindex, "wipe": a.wipe, "required": a.required,
                    "configured": bool(value) if secret else None, "placeholder": a.placeholder or None,
                    "options": [{"value": v, "label": label} for v, label in a.choices] or None,
                    "min": limits.get("ge", limits.get("gt")), "max": limits.get("le", limits.get("lt"))})
    return out
