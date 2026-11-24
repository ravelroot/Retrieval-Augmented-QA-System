from __future__ import annotations

import hashlib
import importlib.util
import math
import re
import time
from typing import Any

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import MetadataMode, NodeWithScore, QueryBundle

from nexo.config import Settings


CONTEXT_WINDOW = 32768
MAX_ANSWER_TOKENS = 1024

LLM_PROVIDERS = {"ollama": "Ollama", "openai": "OpenAI", "compativel": "Compatível com OpenAI", "extrativo": "Extrativo"}


class ProviderError(RuntimeError):
    pass


def _need(package: str, extra: str) -> ProviderError:
    return ProviderError(f"Instale o pacote '{package}' para usar {extra} (pip install {package}).")


def build_embedding(s: Settings):
    if s.embed_provider == "hash":
        from nexo.rag.hash_embedding import HashEmbedding
        return HashEmbedding()
    if s.embed_provider == "huggingface":
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        except ImportError as e:
            raise _need("llama-index-embeddings-huggingface", "embeddings do HuggingFace") from e
        return HuggingFaceEmbedding(model_name=s.embed_model, query_instruction=s.embed_query_prefix or None,
                                    text_instruction=s.embed_text_prefix or None)
    if s.embed_provider == "openai":
        try:
            from llama_index.embeddings.openai import OpenAIEmbedding
        except ImportError as e:
            raise _need("llama-index-embeddings-openai", "embeddings da OpenAI") from e
        if not s.openai_api_key and not s.openai_base_url:
            raise ProviderError("Defina OPENAI_API_KEY para usar embeddings da OpenAI.")
        return OpenAIEmbedding(model=s.embed_model, api_key=s.openai_api_key, api_base=s.openai_base_url)
    if s.embed_provider == "ollama":
        try:
            from llama_index.embeddings.ollama import OllamaEmbedding
        except ImportError as e:
            raise _need("llama-index-embeddings-ollama", "embeddings do Ollama") from e
        return OllamaEmbedding(model_name=s.embed_model, base_url=s.ollama_url)
    raise ProviderError(f"Provedor de embeddings desconhecido: {s.embed_provider}")


def ollama_context(s: Settings) -> int:
    if s.ollama_context:
        return s.ollama_context
    needed = s.top_n * s.chunk_size * 1.3 + 3072
    return min(32768, max(8192, math.ceil(needed / 1024) * 1024))


def keep_alive(value: str) -> int | str:
    text = value.strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else text


def _family(model: str) -> str:
    return model.lower().rsplit("/", 1)[-1]


def reasoning_effort(s: Settings) -> str | None:
    url = (s.openai_base_url or "").lower()
    family = _family(s.llm_model)
    if ("api.groq.com" in url and family.startswith("gpt-oss")) or (
            "generativelanguage.googleapis.com" in url and family.startswith("gemini")):
        return "low"
    return None


def build_llm(s: Settings):
    if s.llm_provider == "extrativo":
        return None
    if s.llm_provider == "ollama":
        try:
            from llama_index.llms.ollama import Ollama
        except ImportError as e:
            raise _need("llama-index-llms-ollama", "o Ollama") from e
        return Ollama(model=s.llm_model, base_url=s.ollama_url, temperature=s.llm_temperature,
                      request_timeout=s.llm_timeout, context_window=ollama_context(s), keep_alive=keep_alive(s.ollama_keep_alive),
                      thinking="low" if _family(s.llm_model).startswith("gpt-oss") else False,
                      additional_kwargs={"num_predict": MAX_ANSWER_TOKENS})
    if s.llm_provider == "openai":
        try:
            from llama_index.llms.openai import OpenAI
        except ImportError as e:
            raise _need("llama-index-llms-openai", "a OpenAI") from e
        if not s.openai_api_key and not s.openai_base_url:
            raise ProviderError("Defina OPENAI_API_KEY para usar a OpenAI.")
        return OpenAI(model=s.llm_model, api_key=s.openai_api_key, api_base=s.openai_base_url,
                      temperature=s.llm_temperature, timeout=s.llm_timeout)
    if s.llm_provider == "compativel":
        try:
            from llama_index.llms.openai_like import OpenAILike
        except ImportError as e:
            raise _need("llama-index-llms-openai-like", "um serviço compatível com a OpenAI") from e
        if not s.openai_base_url:
            raise ProviderError("Informe o endereço do serviço compatível com a OpenAI (NEXO_OPENAI_BASE_URL).")
        effort = reasoning_effort(s)
        return OpenAILike(model=s.llm_model, api_base=s.openai_base_url, api_key=s.openai_api_key or "sem-chave",
                          temperature=s.llm_temperature, timeout=s.llm_timeout, is_chat_model=True,
                          context_window=CONTEXT_WINDOW, max_retries=1,
                          additional_kwargs={"reasoning_effort": effort} if effort else {})
    raise ProviderError(f"Provedor de LLM desconhecido: {s.llm_provider}")


def preload(llm: Any, s: Settings) -> None:
    if s.llm_provider == "ollama" and llm is not None:
        llm.client.generate(model=llm.model, prompt="", keep_alive=llm.keep_alive, options={"num_ctx": llm.context_window})


def build_vector_store(s: Settings):
    if s.vector_store == "chroma":
        import chromadb
        from llama_index.vector_stores.chroma import ChromaVectorStore
        if s.chroma_host:
            client = chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port)
        else:
            s.chroma_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(s.chroma_path))
        collection = client.get_or_create_collection(s.collection, metadata={"hnsw:space": "cosine"})
        return ChromaVectorStore(chroma_collection=collection), {"client": client, "collection": collection}
    if s.vector_store == "qdrant":
        try:
            from llama_index.vector_stores.qdrant import QdrantVectorStore
            from qdrant_client import QdrantClient
        except ImportError as e:
            raise _need("llama-index-vector-stores-qdrant", "o Qdrant") from e
        if s.qdrant_url:
            client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)
        else:
            s.qdrant_path.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=str(s.qdrant_path))
        return QdrantVectorStore(client=client, collection_name=s.collection), {"client": client}
    raise ProviderError(f"Banco vetorial desconhecido: {s.vector_store}")


class CrossEncoderRerank(BaseNodePostprocessor):
    model: str
    _encoder: Any = PrivateAttr()

    def __init__(self, model: str):
        super().__init__(model=model)
        import torch
        from llama_index.core.utils import infer_torch_device
        from sentence_transformers import CrossEncoder
        self._encoder = CrossEncoder(model, device=infer_torch_device(), max_length=512, trust_remote_code=False,
                                     activation_fn=torch.nn.Sigmoid())

    @classmethod
    def class_name(cls) -> str:
        return "NexoCrossEncoderRerank"

    def _postprocess_nodes(self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None) -> list[NodeWithScore]:
        if not nodes or query_bundle is None:
            return list(nodes)
        pairs = [(query_bundle.query_str, n.node.get_content(metadata_mode=MetadataMode.EMBED)) for n in nodes]
        scores = self._encoder.predict(pairs, batch_size=min(len(pairs), 16), show_progress_bar=False)
        for node, score in zip(nodes, scores):
            node.score = float(score)
        return sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)


def build_reranker(s: Settings) -> Any:
    if s.reranker == "none":
        return None
    if s.reranker == "huggingface":
        if importlib.util.find_spec("sentence_transformers") is None:
            raise _need("sentence-transformers", "o reranking do HuggingFace")
        return CrossEncoderRerank(model=s.rerank_model)
    if s.reranker == "cohere":
        try:
            from llama_index.postprocessor.cohere_rerank import CohereRerank
        except ImportError as e:
            raise _need("llama-index-postprocessor-cohere-rerank", "o reranking da Cohere") from e
        if not s.cohere_api_key:
            raise ProviderError("Defina COHERE_API_KEY para usar o reranking da Cohere.")
        return CohereRerank(api_key=s.cohere_api_key, model=s.cohere_model, top_n=s.top_n)
    raise ProviderError(f"Reranker desconhecido: {s.reranker}")


def cited(text: str, sources: list) -> list:
    ranks = {int(n) for n in re.findall(r"\[(\d{1,2})\]", text or "")}
    picked = [x for x in sources if getattr(x, "rank", None) in ranks]
    return picked or list(sources)


def embedding_space(s: Settings) -> str:
    parts = [s.embed_provider, s.embed_model, s.embed_query_prefix, s.embed_text_prefix]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _short(error: Exception) -> str:
    text = str(error).strip().splitlines()[0] if str(error).strip() else error.__class__.__name__
    return text[:300]


def probe(target: str, s: Settings) -> dict:
    started = time.perf_counter()
    try:
        if target == "llm":
            llm = build_llm(s)
            if llm is None:
                return {"ok": True, "detail": "Modo extrativo: as respostas são montadas com frases dos trechos, sem modelo.",
                        "latency_ms": 0}
            text = llm.complete("Responda apenas com a palavra: ok").text.strip()
            detail = f"{LLM_PROVIDERS.get(s.llm_provider, s.llm_provider)} respondeu com {s.llm_model}"
            if text:
                detail += f": “{text[:60]}”"
        elif target == "embedding":
            vector = build_embedding(s).get_text_embedding("teste de conexão do Nexo")
            name = "o embedding léxico de teste" if s.embed_provider == "hash" else s.embed_model
            detail = f"Embeddings funcionando: vetores de {len(vector)} dimensões com {name}."
        elif target == "reranker":
            reranker = build_reranker(s)
            if reranker is None:
                return {"ok": True, "detail": "Reranking desligado: a ordem da busca vetorial é mantida.", "latency_ms": 0}
            from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
            nodes = [NodeWithScore(node=TextNode(text="O filtro deve ser trocado a cada seis meses."), score=0.5),
                     NodeWithScore(node=TextNode(text="A garantia cobre defeitos de fabricação."), score=0.5)]
            ranked = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle("Quando trocar o filtro?"))
            detail = f"Reranking funcionando: {len(ranked)} trecho(s) reordenado(s)."
        else:
            raise ProviderError("Teste desconhecido.")
    except ProviderError as e:
        return {"ok": False, "detail": str(e), "latency_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as e:
        return {"ok": False, "detail": f"Falhou: {_short(e)}", "latency_ms": int((time.perf_counter() - started) * 1000)}
    return {"ok": True, "detail": detail, "latency_ms": int((time.perf_counter() - started) * 1000)}


def index_signature(s: Settings) -> str:
    parts = [s.embed_provider, s.embed_model, s.embed_query_prefix, s.embed_text_prefix, str(s.chunk_size),
             str(s.chunk_overlap), s.vector_store, s.collection]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def describe(s: Settings) -> dict:
    if s.llm_provider == "extrativo":
        llm = "Extrativo (sem LLM)"
    elif s.llm_provider == "compativel":
        llm = f"compatível · {s.llm_model} em {s.openai_base_url or 'endereço não informado'}"
    else:
        llm = f"{s.llm_provider} · {s.llm_model}"
    embed = "Hash léxico (testes)" if s.embed_provider == "hash" else f"{s.embed_provider} · {s.embed_model}"
    if s.reranker == "none":
        rerank = "Desligado"
    elif s.reranker == "cohere":
        rerank = f"cohere · {s.cohere_model}"
    else:
        rerank = f"huggingface · {s.rerank_model}"
    if s.vector_store == "chroma":
        store = f"ChromaDB · {'servidor ' + s.chroma_host if s.chroma_host else 'local'}"
    else:
        store = f"Qdrant · {'servidor' if s.qdrant_url else 'local'}"
    return {"llm": llm, "embedding": embed, "reranker": rerank, "vector_store": store, "collection": s.collection,
            "chunk_size": s.chunk_size, "chunk_overlap": s.chunk_overlap, "top_k": s.top_k, "top_n": s.top_n,
            "min_similarity": s.min_similarity, "min_rerank_score": s.min_rerank_score,
            "verify_answers": s.verify_answers, "temperature": s.llm_temperature, "history_turns": s.history_turns,
            "signature": index_signature(s)}
