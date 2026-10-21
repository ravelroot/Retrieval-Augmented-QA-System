import math

from llama_index.core.postprocessor.types import BaseNodePostprocessor

from nexo.config import Settings
from nexo.rag.engine import NOT_FOUND, RagEngine
from nexo.rag.hash_embedding import HashEmbedding
from tests.conftest import FIXTURES


class ReverseReranker(BaseNodePostprocessor):
    def _postprocess_nodes(self, nodes, query_bundle=None):
        out = list(reversed(nodes))
        for i, n in enumerate(out):
            n.score = 0.9 - i * 0.3
        return out


def make_engine(tmp_path, **kw) -> RagEngine:
    s = Settings(data_dir=tmp_path, embed_provider="hash", llm_provider="extrativo", reranker="none",
                 min_similarity=0.1, **kw)
    e = RagEngine(s)
    e.ingest("d1", "Manual", "manual.pdf", FIXTURES / "manual-exemplo.pdf")
    return e


def test_hash_embedding_is_normalized_and_lexical():
    emb = HashEmbedding()
    a = emb.get_text_embedding("botão RESET pressionado por 15 segundos")
    b = emb.get_query_embedding("Como usar o botão reset?")
    c = emb.get_query_embedding("temperatura de operação")
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-6)
    dot = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert dot(a, b) > dot(a, c)


def test_reranker_reorders_and_threshold_filters(tmp_path):
    e = make_engine(tmp_path, top_n=3, min_rerank_score=0.5)
    e._reranker = ReverseReranker()
    e._reranker_loaded = True
    nodes = e.retrieve("firmware atualização falhar modo de recuperação", None)
    assert 1 <= len(nodes) <= 2
    assert all(n.score >= 0.5 for n in nodes)
    answer = e.ask("firmware atualização falhar modo de recuperação", [], None)
    assert answer.sources[0].rerank_score is not None
    assert answer.sources[0].similarity is not None


def test_not_found_without_relevant_context(tmp_path):
    e = make_engine(tmp_path)
    a = e.ask("Receita de bolo de chocolate com cobertura", [], None)
    assert a.answered is False
    assert a.text == NOT_FOUND


def test_scope_filter(tmp_path):
    e = make_engine(tmp_path)
    assert e.retrieve("firmware", ["outro"]) == []
    assert e.retrieve("firmware", ["d1"])
