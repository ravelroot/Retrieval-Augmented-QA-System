from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexo import db, jobs, knowledge

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "exemplos" / "base-de-teste"
BASE_NAME = "Base de teste"
BASE_DESCRIPTION = "Arquivos fictícios do Roteador RX-200 em PDF, Markdown, HTML, CSV, JSON e TXT, para testar o Nexo."
BOT_NAME = "Agente de teste"
FILES = ("manual-roteador-rx200.pdf", "garantia.md", "perguntas-frequentes.html", "planos-de-suporte.csv",
         "horario-de-atendimento.txt", "especificacoes.json")
TITLES = {"planos-de-suporte.csv": "Planos de suporte", "horario-de-atendimento.txt": "Horário de atendimento",
          "especificacoes.json": "Especificações do RX-200"}
SUGGESTIONS = ("Como restaurar as configurações de fábrica?", "Quanto tempo dura a garantia?",
               "Quantos aparelhos posso conectar ao mesmo tempo?", "O suporte atende aos sábados?")


class SampleError(RuntimeError):
    pass


@dataclass
class SampleResult:
    base: db.KnowledgeBaseRow
    bot: db.BotRow
    added: list[str] = field(default_factory=list)
    existed: bool = False


def _title(path: Path, extension: str) -> str:
    if path.name in TITLES:
        return TITLES[path.name]
    try:
        if extension == "pdf":
            meta = PdfReader(str(path)).metadata
            if meta and meta.title and meta.title.strip():
                return meta.title.strip()[:200]
        else:
            found = knowledge.read_file(path, extension).title
            if found:
                return found[:200]
    except Exception:
        pass
    return path.stem[:200]


def create(database: Session, username: str, enqueue: bool = True) -> SampleResult:
    missing = [name for name in FILES if not (SAMPLE_DIR / name).is_file()]
    if missing:
        raise SampleError(f"Os arquivos de exemplo não estão em exemplos/base-de-teste ({', '.join(missing)}).")
    base = database.scalar(select(db.KnowledgeBaseRow).where(func.lower(db.KnowledgeBaseRow.name) == BASE_NAME.lower()))
    existed = base is not None
    if base is None:
        base = db.KnowledgeBaseRow(name=BASE_NAME, description=BASE_DESCRIPTION, color="#2b4c5a", is_default=False,
                                   created_by=username)
        database.add(base)
        database.flush()
    added: list[db.DocumentRow] = []
    written: list[Path] = []
    for name in FILES:
        source = SAMPLE_DIR / name
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if database.scalar(select(db.DocumentRow.id).where(db.DocumentRow.base_id == base.id, db.DocumentRow.sha256 == digest)):
            continue
        extension = knowledge.extension_of(name)
        row = db.DocumentRow(title=_title(source, extension), filename=name, sha256=digest, size_bytes=len(data),
                             uploaded_by=username, status="PENDING", base_id=base.id, kind=knowledge.kind_of(extension),
                             extension=extension)
        database.add(row)
        database.flush()
        target = jobs.stored_file(row)
        target.write_bytes(data)
        written.append(target)
        added.append(row)
    bot = database.scalar(select(db.BotRow).where(db.BotRow.name == BOT_NAME, db.BotRow.base_id == base.id))
    if bot is None:
        bot = db.BotRow(name=BOT_NAME, base_id=base.id, color="#2b4c5a",
                        description="Responde dúvidas sobre o Roteador RX-200 usando só a Base de teste.",
                        instructions="Responda de forma curta e cordial, em passos quando for um procedimento.",
                        greeting="Olá! Sou o agente de teste do Nexo. Pergunte sobre o Roteador RX-200: instalação, "
                                 "garantia, planos de suporte ou horários.",
                        fallback="Não encontrei isso na Base de teste. Experimente uma das perguntas sugeridas.",
                        suggestions="\n".join(SUGGESTIONS), created_by=username)
        database.add(bot)
    try:
        database.commit()
    except Exception:
        database.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    database.refresh(bot)
    if enqueue:
        for row in added:
            jobs.enqueue(row.id)
    return SampleResult(base=base, bot=bot, added=[r.id for r in added], existed=existed)
