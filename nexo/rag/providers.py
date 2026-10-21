from __future__ import annotations

from typing import Any

from nexo.config import Settings


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


def build_llm(s: Settings):
    if s.llm_provider == "extrativo":
        return None
    if s.llm_provider == "ollama":
        try:
            from llama_index.llms.ollama import Ollama
        except ImportError as e:
            raise _need("llama-index-llms-ollama", "o Ollama") from e
        return Ollama(model=s.llm_model, base_url=s.ollama_url, temperature=s.llm_temperature,
                      request_timeout=s.llm_timeout)
    if s.llm_provider == "openai":
        try:
            from llama_index.llms.openai import OpenAI
        except ImportError as e:
            raise _need("llama-index-llms-openai", "a OpenAI") from e
        if not s.openai_api_key and not s.openai_base_url:
            raise ProviderError("Defina OPENAI_API_KEY para usar a OpenAI.")
        return OpenAI(model=s.llm_model, api_key=s.openai_api_key, api_base=s.openai_base_url,
                      temperature=s.llm_temperature, timeout=s.llm_timeout)
    raise ProviderError(f"Provedor de LLM desconhecido: {s.llm_provider}")


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


def build_reranker(s: Settings) -> Any:
    if s.reranker == "none":
        return None
    if s.reranker == "huggingface":
        try:
            from llama_index.core.postprocessor import SentenceTransformerRerank
            import sentence_transformers
        except ImportError as e:
            raise _need("sentence-transformers", "o reranking do HuggingFace") from e
        return SentenceTransformerRerank(model=s.rerank_model, top_n=s.top_n)
    if s.reranker == "cohere":
        try:
            from llama_index.postprocessor.cohere_rerank import CohereRerank
        except ImportError as e:
            raise _need("llama-index-postprocessor-cohere-rerank", "o reranking da Cohere") from e
        if not s.cohere_api_key:
            raise ProviderError("Defina COHERE_API_KEY para usar o reranking da Cohere.")
        return CohereRerank(api_key=s.cohere_api_key, model=s.cohere_model, top_n=s.top_n)
    raise ProviderError(f"Reranker desconhecido: {s.reranker}")


def describe(s: Settings) -> dict:
    llm = "Extrativo (sem LLM)" if s.llm_provider == "extrativo" else f"{s.llm_provider} · {s.llm_model}"
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
            "verify_answers": s.verify_answers}
