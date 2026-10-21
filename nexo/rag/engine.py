from __future__ import annotations

import logging
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter, MetadataFilters
from pypdf import PdfReader

from nexo.config import Settings
from nexo.rag import providers
from nexo.rag.hash_embedding import tokens

log = logging.getLogger("nexo.rag")

NOT_FOUND = "Não encontrei essa informação nos documentos selecionados."

ANSWER_PROMPT = """Você é o Nexo, um assistente que responde dúvidas sobre manuais técnicos e livros.
Regras obrigatórias:
1. Use somente as informações dos trechos numerados abaixo. Não use conhecimento próprio.
2. Se os trechos não trazem a resposta, responda exatamente: "{not_found}"
3. Cite a fonte de cada afirmação com o número do trecho entre colchetes, por exemplo [1] ou [2][3].
4. Seja direto e preciso. Mantenha termos técnicos, valores, unidades e passos como aparecem nos trechos.
5. Responda no mesmo idioma da pergunta.

Trechos:
{context}

Pergunta: {question}
Resposta:"""

CONDENSE_PROMPT = """Reescreva a última pergunta do usuário como uma pergunta completa e independente, usando a conversa
anterior apenas para resolver referências como "isso", "ele" ou "o passo anterior". Não responda a pergunta.

Conversa anterior:
{history}

Última pergunta: {question}
Pergunta independente:"""


class IngestionError(RuntimeError):
    pass


@dataclass
class Source:
    document_id: str
    document_title: str
    chunk_id: str
    page: int
    rank: int
    similarity: float | None
    rerank_score: float | None
    excerpt: str


@dataclass
class Answer:
    text: str
    answered: bool
    sources: list[Source] = field(default_factory=list)
    grounded: bool | None = None
    model: str = ""
    latency_ms: int = 0
    standalone_question: str = ""


@dataclass
class PdfContent:
    title: str | None
    pages: list[tuple[int, str]]
    total_pages: int


def _join_lines(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            out.append("")
            continue
        prev = out[-1] if out else ""
        if prev and len(prev.rsplit("\n", 1)[-1]) >= 50 and prev[-1] not in ".:;!?":
            out[-1] = f"{prev} {line}"
        else:
            out.append(line)
    return "\n".join(out)


def read_pdf(path: Path) -> PdfContent:
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        raise IngestionError(f"Não foi possível abrir o PDF: {e}") from e
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as e:
            raise IngestionError("O PDF está protegido por senha.") from e
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        text = _join_lines(text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) >= 20:
            pages.append((i, text))
    title = None
    try:
        meta = reader.metadata
        if meta and meta.title and meta.title.strip():
            title = meta.title.strip()[:200]
    except Exception:
        title = None
    return PdfContent(title=title, pages=pages, total_pages=len(reader.pages))


class RagEngine:
    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.RLock()
        self._index: VectorStoreIndex | None = None
        self._vector_store = None
        self._handles: dict = {}
        self._embed = None
        self._llm = None
        self._llm_loaded = False
        self._reranker = None
        self._reranker_loaded = False
        self.splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)

    def _ensure_index(self) -> VectorStoreIndex:
        with self._lock:
            if self._index is None:
                self._embed = providers.build_embedding(self.s)
                self._vector_store, self._handles = providers.build_vector_store(self.s)
                self._index = VectorStoreIndex.from_vector_store(self._vector_store, embed_model=self._embed)
            return self._index

    def llm(self):
        with self._lock:
            if not self._llm_loaded:
                self._llm = providers.build_llm(self.s)
                self._llm_loaded = True
            return self._llm

    def reranker(self):
        with self._lock:
            if not self._reranker_loaded:
                self._reranker = providers.build_reranker(self.s)
                self._reranker_loaded = True
            return self._reranker

    def model_name(self) -> str:
        return "extrativo" if self.s.llm_provider == "extrativo" else f"{self.s.llm_provider}:{self.s.llm_model}"

    def ingest(self, document_id: str, title: str, filename: str, path: Path) -> tuple[int, int, str | None]:
        content = read_pdf(path)
        if not content.pages:
            raise IngestionError("O PDF não tem texto selecionável. Se for digitalizado, aplique OCR antes de enviar.")
        docs = [
            Document(
                text=text,
                metadata={"source_id": document_id, "title": title, "filename": filename, "page": page},
                excluded_embed_metadata_keys=["source_id", "filename", "page", "chunk_index"],
                excluded_llm_metadata_keys=["source_id", "filename", "chunk_index"],
            )
            for page, text in content.pages
        ]
        nodes = self.splitter.get_nodes_from_documents(docs)
        for i, node in enumerate(nodes):
            node.id_ = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nexo:{document_id}:{i}"))
            node.metadata["chunk_index"] = i
        index = self._ensure_index()
        with self._lock:
            self.delete(document_id)
            batch = 64
            for start in range(0, len(nodes), batch):
                index.insert_nodes(nodes[start:start + batch])
        return content.total_pages, len(nodes), content.title

    def delete(self, document_id: str) -> None:
        self._ensure_index()
        with self._lock:
            if self.s.vector_store == "chroma":
                self._handles["collection"].delete(where={"source_id": document_id})
            elif self._handles["client"].collection_exists(self.s.collection):
                filters = MetadataFilters(filters=[MetadataFilter(key="source_id", value=document_id)])
                self._vector_store.delete_nodes(filters=filters)

    def count(self) -> int | None:
        try:
            self._ensure_index()
            if self.s.vector_store == "chroma":
                return self._handles["collection"].count()
            return None
        except Exception:
            return None

    def _condense(self, question: str, history: list[tuple[str, str]]) -> str:
        llm = self.llm()
        if llm is None or not history:
            return question
        lines = "\n".join(f"{'Usuário' if role == 'user' else 'Nexo'}: {text[:800]}" for role, text in history)
        try:
            out = llm.complete(CONDENSE_PROMPT.format(history=lines, question=question)).text.strip()
            return out.splitlines()[0].strip() if out else question
        except Exception as e:
            log.warning("Falha ao reescrever a pergunta: %s", e)
            return question

    def retrieve(self, question: str, document_ids: list[str] | None, rerank: bool = True) -> list[NodeWithScore]:
        index = self._ensure_index()
        filters = None
        if document_ids:
            if len(document_ids) == 1:
                filters = MetadataFilters(filters=[MetadataFilter(key="source_id", value=document_ids[0])])
            else:
                filters = MetadataFilters(filters=[MetadataFilter(key="source_id", value=document_ids,
                                                                  operator=FilterOperator.IN)])
        retriever = index.as_retriever(similarity_top_k=self.s.top_k, filters=filters)
        found = retriever.retrieve(question)
        for n in found:
            n.score = self._cosine(n.score)
            n.node.metadata["_similarity"] = n.score
        nodes = [n for n in found if n.score >= self.s.min_similarity]
        if not rerank:
            return nodes[: self.s.top_n]
        reranker = self.reranker()
        if reranker is None or not nodes:
            return nodes[: self.s.top_n]
        ranked = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(question))
        return [n for n in ranked if (n.score or 0.0) >= self.s.min_rerank_score][: self.s.top_n]

    def _cosine(self, score: float | None) -> float:
        if score is None:
            return 0.0
        if self.s.vector_store == "chroma":
            return 1.0 + math.log(max(score, 1e-9))
        return float(score)

    def ask(self, question: str, history: list[tuple[str, str]], document_ids: list[str] | None) -> Answer:
        started = time.perf_counter()
        standalone = self._condense(question, history[-2 * self.s.history_turns:] if self.s.history_turns else [])
        nodes = self.retrieve(standalone, document_ids)
        sources = [self._source(n, i) for i, n in enumerate(nodes, start=1)]
        if not nodes:
            return Answer(NOT_FOUND, False, [], None, self.model_name(), self._ms(started), standalone)
        llm = self.llm()
        if llm is None:
            text = self._extractive(standalone, nodes)
            return Answer(text, True, sources, True, self.model_name(), self._ms(started), standalone)
        context = "\n\n".join(
            f"[{i}] {n.node.metadata.get('title', '')} — página {n.node.metadata.get('page', '?')}\n{n.node.get_content()}"
            for i, n in enumerate(nodes, start=1)
        )
        prompt = ANSWER_PROMPT.format(not_found=NOT_FOUND, context=context, question=standalone)
        text = llm.complete(prompt).text.strip()
        answered = NOT_FOUND.lower()[:30] not in text.lower()
        grounded = self._verify(standalone, text, nodes) if answered and self.s.verify_answers else None
        if not answered:
            sources = []
        return Answer(text, answered, sources, grounded, self.model_name(), self._ms(started), standalone)

    def _verify(self, question: str, answer: str, nodes: list[NodeWithScore]) -> bool | None:
        try:
            from llama_index.core.evaluation import FaithfulnessEvaluator
            result = FaithfulnessEvaluator(llm=self.llm()).evaluate(
                query=question, response=answer, contexts=[n.node.get_content() for n in nodes])
            return bool(result.passing)
        except Exception as e:
            log.warning("Falha na verificação da resposta: %s", e)
            return None

    def _extractive(self, question: str, nodes: list[NodeWithScore]) -> str:
        q = set(tokens(question))
        picked: list[tuple[float, int, str]] = []
        for i, n in enumerate(nodes, start=1):
            sentences = re.split(r"(?<=[.!?])\s+|\n+", n.node.get_content())
            for pos, sent in enumerate(sentences):
                sent = sent.strip()
                if len(sent) < 25:
                    continue
                overlap = len(q & set(tokens(sent)))
                if overlap:
                    picked.append((overlap - pos * 0.01 - i * 0.05, i, sent))
        if not picked:
            picked = [(0.0, i, n.node.get_content().strip()[:400]) for i, n in enumerate(nodes[:2], start=1)]
        picked.sort(key=lambda t: t[0], reverse=True)
        if picked and picked[0][0] > 0:
            best = picked[0][0]
            picked = [t for t in picked if t[0] >= best * 0.5]
        seen: set[str] = set()
        lines = []
        for _, i, sent in picked:
            if sent in seen:
                continue
            seen.add(sent)
            lines.append(f"- {sent} [{i}]")
            if len(lines) == 4:
                break
        return "Trechos dos documentos que respondem à pergunta:\n\n" + "\n".join(lines)

    @staticmethod
    def _source(n: NodeWithScore, rank: int) -> Source:
        meta = n.node.metadata
        similarity = meta.get("_similarity")
        rerank = n.score if similarity is not None and n.score != similarity else None
        text = n.node.get_content().strip()
        return Source(document_id=meta.get("source_id", ""), document_title=meta.get("title", ""),
                      chunk_id=n.node.node_id, page=int(meta.get("page", 0)), rank=rank,
                      similarity=round(float(similarity), 4) if similarity is not None else None,
                      rerank_score=round(float(rerank), 4) if rerank is not None else None,
                      excerpt=text[:1200])

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)


_engine: RagEngine | None = None
_engine_lock = threading.Lock()


def get_engine(settings: Settings) -> RagEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = RagEngine(settings)
        return _engine


def reset_engine() -> None:
    global _engine
    with _engine_lock:
        _engine = None
