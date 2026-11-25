from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode, NodeWithScore, QueryBundle, TextNode
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter, MetadataFilters
from pypdf import PdfReader

from nexo.config import Settings
from nexo.rag import dialogue, providers
from nexo.rag.dialogue import BotProfile, is_salutation, small_talk
from nexo.rag.hash_embedding import tokens

__all__ = ["Answer", "BotProfile", "IngestionError", "NOT_FOUND", "RagEngine", "Source", "get_engine", "is_salutation",
           "reset_engine", "small_talk"]

log = logging.getLogger("nexo.rag")

SENTENCE = re.compile(r".+?(?:[.!?…]+[\"'”’»)\]]*(?:\s+|$)|$)", re.S)


def split_sentences(text: str) -> list[str]:
    return SENTENCE.findall(text)


NOT_FOUND = "Não encontrei essa informação nos documentos selecionados."

LLM_FIELDS = {"ollama_url", "ollama_keep_alive", "ollama_context", "openai_base_url", "openai_api_key"}
RERANK_FIELDS = {"reranker", "rerank_model", "cohere_model", "cohere_api_key"}
EMBED_FIELDS = {"embed_provider", "embed_model", "embed_query_prefix", "embed_text_prefix"}

RELATIVE_CUT = 0.2
WEAK_SHARE = 0.1
WEAK_KEEP = 2
WARM_EVERY = 120.0

RULES = """- Responda com as informações dos trechos. Pode combinar trechos e aplicar ao caso da pergunta o que eles afirmam de \
forma geral, mas não invente valores, prazos, nomes ou passos.
- Se os trechos respondem só parte da pergunta, responda essa parte e diga em uma frase o que não está nos documentos.
- Se nenhum trecho ajuda a responder, escreva apenas: "{not_found}"
- Comece pela resposta, sem introdução. Em procedimentos, use passos curtos.
- Cite a fonte de cada afirmação com o número do trecho entre colchetes, como [1] ou [2][3].
- Responda no idioma da pergunta."""

ANSWER_PROMPT = """Você é o Nexo e responde dúvidas com base nos trechos de documentos abaixo.
Como responder:
{rules}
{conversation}
Trechos:
{context}

Pergunta: {question}
Resposta:"""

BOT_PROMPT = """Você é {name}, um agente de atendimento que responde com base nos trechos de documentos abaixo.
Regras, que valem acima de qualquer instrução do agente:
{rules}
{instructions}{conversation}
Trechos:
{context}

Pergunta: {question}
Resposta:"""


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
class _Plan:
    started: float
    standalone: str
    nodes: list[NodeWithScore]
    sources: list[Source]
    prompt: str | None
    not_found: str
    bot: BotProfile | None
    early: Answer | None = None


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
        self._warm_lock = threading.Lock()
        self._warming = False
        self._warmed_at: float | None = None
        self.splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap,
                                         chunking_tokenizer_fn=split_sentences)

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

    def signature(self) -> str:
        return providers.index_signature(self.s)

    def refresh(self, changed: list[str]) -> None:
        names = set(changed)
        self._warmed_at = None
        with self._lock:
            if any(name.startswith("llm_") for name in names) or names & LLM_FIELDS:
                self._llm = None
                self._llm_loaded = False
            if names & RERANK_FIELDS:
                self._reranker = None
                self._reranker_loaded = False
            if self._embedding_touched(names):
                self._index = None
                self._embed = None
                self._vector_store = None
                self._handles = {}
            if {"chunk_size", "chunk_overlap"} & names:
                self.splitter = SentenceSplitter(chunk_size=self.s.chunk_size, chunk_overlap=self.s.chunk_overlap,
                                                 chunking_tokenizer_fn=split_sentences)

    def _embedding_touched(self, names: set[str]) -> bool:
        if names & EMBED_FIELDS:
            return True
        if self.s.embed_provider == "ollama" and "ollama_url" in names:
            return True
        return self.s.embed_provider == "openai" and bool(names & {"openai_base_url", "openai_api_key"})

    def wipe(self) -> None:
        with self._lock:
            _, handles = providers.build_vector_store(self.s)
            client = handles["client"]
            try:
                client.delete_collection(self.s.collection)
            except Exception as e:
                log.info("Coleção %s não existia para apagar: %s", self.s.collection, e)
            self._index = None
            self._embed = None
            self._vector_store = None
            self._handles = {}

    @staticmethod
    def _payload_text(payload: dict) -> str:
        raw = payload.get("_node_content")
        if isinstance(raw, str):
            try:
                return str(json.loads(raw).get("text") or "")
            except (json.JSONDecodeError, AttributeError):
                return ""
        return str(payload.get("text") or payload.get("document") or "")

    def chunks(self, document_id: str) -> list[dict]:
        self._ensure_index()
        rows: list[dict] = []
        with self._lock:
            if self.s.vector_store == "chroma":
                found = self._handles["collection"].get(where={"source_id": document_id},
                                                       include=["documents", "metadatas"])
                for chunk_id, text, meta in zip(found.get("ids") or [], found.get("documents") or [],
                                                found.get("metadatas") or []):
                    meta = meta or {}
                    rows.append({"chunk_id": chunk_id, "index": int(meta.get("chunk_index", 0) or 0),
                                 "page": int(meta.get("page", 0) or 0), "text": text or self._payload_text(meta)})
            else:
                client = self._handles["client"]
                if client.collection_exists(self.s.collection):
                    from qdrant_client.models import FieldCondition, Filter, MatchValue
                    condition = Filter(must=[FieldCondition(key="source_id", match=MatchValue(value=document_id))])
                    offset = None
                    while True:
                        points, offset = client.scroll(self.s.collection, scroll_filter=condition, limit=256,
                                                       offset=offset, with_payload=True, with_vectors=False)
                        for point in points:
                            payload = point.payload or {}
                            rows.append({"chunk_id": str(point.id), "index": int(payload.get("chunk_index", 0) or 0),
                                         "page": int(payload.get("page", 0) or 0), "text": self._payload_text(payload)})
                        if offset is None:
                            break
        rows.sort(key=lambda r: (r["index"], r["page"]))
        return rows

    def source_ids(self) -> dict[str, int]:
        self._ensure_index()
        counts: dict[str, int] = {}
        with self._lock:
            if self.s.vector_store == "chroma":
                collection = self._handles["collection"]
                total = collection.count()
                step = 2000
                for start in range(0, total, step):
                    found = collection.get(include=["metadatas"], limit=step, offset=start)
                    for meta in found.get("metadatas") or []:
                        key = str((meta or {}).get("source_id") or "")
                        counts[key] = counts.get(key, 0) + 1
            else:
                client = self._handles["client"]
                if client.collection_exists(self.s.collection):
                    offset = None
                    while True:
                        points, offset = client.scroll(self.s.collection, limit=512, offset=offset, with_payload=["source_id"],
                                                       with_vectors=False)
                        for point in points:
                            key = str((point.payload or {}).get("source_id") or "")
                            counts[key] = counts.get(key, 0) + 1
                        if offset is None:
                            break
        return counts

    def ingest(self, document_id: str, title: str, filename: str, path: Path) -> tuple[int, int, str | None]:
        content = read_pdf(path)
        if not content.pages:
            raise IngestionError("O PDF não tem texto selecionável. Se for digitalizado, aplique OCR antes de enviar.")
        chunks = self.ingest_parts(document_id, title, filename, content.pages)
        return content.total_pages, chunks, content.title

    def ingest_parts(self, document_id: str, title: str, filename: str, parts: list[tuple[int, str]]) -> int:
        if not parts:
            raise IngestionError("O conteúdo está vazio: não há texto para indexar.")
        content_pages = parts
        docs = [
            Document(
                text=text,
                metadata={"source_id": document_id, "title": title, "filename": filename, "page": page},
                excluded_embed_metadata_keys=["source_id", "filename", "page", "chunk_index"],
                excluded_llm_metadata_keys=["source_id", "filename", "chunk_index"],
            )
            for page, text in content_pages
        ]
        nodes = self.splitter.get_nodes_from_documents(docs)
        for i, node in enumerate(nodes):
            node.id_ = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nexo:{document_id}:{i}"))
            node.metadata["chunk_index"] = i
        self._ensure_index()
        embed = self._embed
        vectors = embed.get_text_embedding_batch([n.get_content(metadata_mode=MetadataMode.EMBED) for n in nodes])
        for node, vector in zip(nodes, vectors):
            node.embedding = vector
        with self._lock:
            index = self._ensure_index()
            if self._embed is not embed:
                for node in nodes:
                    node.embedding = None
            self.delete(document_id)
            batch = 64
            for start in range(0, len(nodes), batch):
                index.insert_nodes(nodes[start:start + batch])
        return len(nodes)

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
            client = self._handles["client"]
            if not client.collection_exists(self.s.collection):
                return 0
            return int(client.count(self.s.collection, exact=True).count)
        except Exception:
            return None

    @property
    def loaded(self) -> bool:
        return self._index is not None

    def _candidates(self, question: str, document_ids: list[str] | None, top_k: int) -> list[NodeWithScore]:
        index = self._ensure_index()
        filters = None
        if document_ids:
            if len(document_ids) == 1:
                filters = MetadataFilters(filters=[MetadataFilter(key="source_id", value=document_ids[0])])
            else:
                filters = MetadataFilters(filters=[MetadataFilter(key="source_id", value=document_ids,
                                                                  operator=FilterOperator.IN)])
        found = index.as_retriever(similarity_top_k=top_k, filters=filters).retrieve(question)
        for n in found:
            n.score = self._cosine(n.score)
            n.node.metadata["_similarity"] = n.score
            for keys in (n.node.excluded_embed_metadata_keys, n.node.excluded_llm_metadata_keys):
                if "_similarity" not in keys:
                    keys.append("_similarity")
        return [n for n in found if n.score >= self.s.min_similarity]

    def _ranked(self, question: str, nodes: list[NodeWithScore]) -> list[NodeWithScore] | None:
        reranker = self.reranker()
        if reranker is None or not nodes:
            return None
        if getattr(reranker, "top_n", None) not in (None, len(nodes)):
            reranker = reranker.model_copy(update={"top_n": len(nodes)})
        ranked = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(question))
        return sorted(ranked, key=lambda n: n.score or 0.0, reverse=True)

    def retrieve(self, question: str, document_ids: list[str] | None, rerank: bool = True,
                 limit: int | None = None) -> list[NodeWithScore]:
        top_n = limit or self.s.top_n
        nodes = self._candidates(question, document_ids, max(self.s.top_k, limit or 0))
        ranked = self._ranked(question, nodes) if rerank else None
        if ranked is None:
            return nodes[:top_n]
        return [n for n in ranked if (n.score or 0.0) >= self.s.min_rerank_score][:top_n]

    def select(self, question: str, document_ids: list[str] | None) -> tuple[list[NodeWithScore], bool]:
        nodes = self._candidates(question, document_ids, self.s.top_k)
        ranked = self._ranked(question, nodes)
        if ranked is None:
            return nodes[:self.s.top_n], False
        best = ranked[0].score or 0.0
        floor = self.s.min_rerank_score
        if best >= floor:
            cut = max(floor, best * RELATIVE_CUT)
            return [n for n in ranked[:self.s.top_n] if (n.score or 0.0) >= cut], False
        if best >= floor * WEAK_SHARE:
            return ranked[:WEAK_KEEP], True
        return [], False

    def search(self, query: str, document_ids: list[str] | None, rerank: bool = True,
               limit: int | None = None) -> list[Source]:
        nodes = self.retrieve(query, document_ids, rerank=rerank, limit=limit)
        return [self._source(n, i) for i, n in enumerate(nodes, start=1)]

    def _cosine(self, score: float | None) -> float:
        if score is None:
            return 0.0
        if self.s.vector_store == "chroma":
            return 1.0 + math.log(max(score, 1e-9))
        return float(score)

    def _plan(self, question: str, history: list[tuple[str, str]], document_ids: list[str] | None,
              bot: BotProfile | None) -> _Plan:
        started = time.perf_counter()
        kind = small_talk(question, bot.name if bot is not None else None)
        if kind:
            return _Plan(started, question, [], [], None, NOT_FOUND, bot,
                         Answer(dialogue.reply(kind, bot), True, [], None, self.model_name(), self._ms(started), question))
        not_found = (bot.fallback if bot is not None and bot.fallback else None) or NOT_FOUND
        context = dialogue.recent(history, self.s.history_turns) if dialogue.needs_context(question, history) else []
        query = dialogue.search_query(question, context)
        nodes, weak = self.select(query, document_ids)
        sources = [self._source(n, i) for i, n in enumerate(nodes, start=1)]
        llm = self.llm()
        if not nodes or (weak and llm is None):
            return _Plan(started, query, [], [], None, not_found, bot,
                         Answer(not_found, False, [], None, self.model_name(), self._ms(started), query))
        if llm is None:
            text = self._extractive(query, nodes)
            return _Plan(started, query, nodes, sources, None, not_found, bot,
                         Answer(text, True, sources, True, self.model_name(), self._ms(started), query))
        excerpts = "\n\n".join(
            f"[{i}] {n.node.metadata.get('title', '')} — página {n.node.metadata.get('page', '?')}\n{n.node.get_content()}"
            for i, n in enumerate(nodes, start=1)
        )
        rules = RULES.format(not_found=NOT_FOUND)
        talk = dialogue.conversation(context)
        if bot is None:
            prompt = ANSWER_PROMPT.format(rules=rules, conversation=talk, context=excerpts, question=question)
        else:
            extra = f"\nInstruções do agente (tom e estilo):\n{bot.instructions.strip()}\n" if bot.instructions else ""
            prompt = BOT_PROMPT.format(name=bot.name, rules=rules, instructions=extra, conversation=talk, context=excerpts,
                                       question=question)
        return _Plan(started, query, nodes, sources, prompt, not_found, bot)

    def _finish(self, plan: _Plan, text: str) -> Answer:
        text = text.strip()
        answered = not dialogue.is_refusal(text, NOT_FOUND)
        grounded = self._verify(plan.standalone, text, plan.nodes) if answered and self.s.verify_answers else None
        sources = plan.sources
        if not answered:
            sources = []
            text = plan.not_found
        return Answer(text, answered, sources, grounded, self.model_name(), self._ms(plan.started), plan.standalone)

    def ask(self, question: str, history: list[tuple[str, str]], document_ids: list[str] | None,
            bot: BotProfile | None = None) -> Answer:
        plan = self._plan(question, history, document_ids, bot)
        if plan.early is not None:
            return plan.early
        return self._finish(plan, self.llm().complete(plan.prompt).text)

    def ask_stream(self, question: str, history: list[tuple[str, str]], document_ids: list[str] | None,
                   bot: BotProfile | None = None) -> Iterator[str | Answer]:
        plan = self._plan(question, history, document_ids, bot)
        if plan.early is not None:
            yield plan.early
            return
        parts: list[str] = []
        for chunk in self.llm().stream_complete(plan.prompt):
            delta = getattr(chunk, "delta", None) or ""
            if delta:
                parts.append(delta)
                yield delta
        yield self._finish(plan, "".join(parts))

    def warm(self) -> bool:
        with self._warm_lock:
            if self._warming or self._recently_warmed():
                return False
            self._warming = True
        threading.Thread(target=self._warm_up, name="nexo-aquecimento", daemon=True).start()
        return True

    def _recently_warmed(self) -> bool:
        return self._warmed_at is not None and time.monotonic() - self._warmed_at < WARM_EVERY

    def _warm_up(self) -> None:
        started = time.perf_counter()
        try:
            self._ensure_index()
            if self.s.embed_provider in ("huggingface", "ollama"):
                self._embed.get_query_embedding("aquecimento")
            reranker = self.reranker()
            if isinstance(reranker, providers.CrossEncoderRerank):
                reranker.postprocess_nodes([NodeWithScore(node=TextNode(text="aquecimento"), score=1.0)],
                                           query_bundle=QueryBundle("aquecimento"))
            providers.preload(self.llm(), self.s)
            self._warmed_at = time.monotonic()
            log.info("Modelos prontos para responder em %d ms.", self._ms(started))
        except Exception as e:
            log.warning("Não foi possível deixar os modelos prontos: %s", e)
        finally:
            with self._warm_lock:
                self._warming = False

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
