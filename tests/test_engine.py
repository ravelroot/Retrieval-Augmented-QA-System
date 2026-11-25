import math
import time
from types import SimpleNamespace

from llama_index.core.postprocessor.types import BaseNodePostprocessor

from nexo.config import Settings
from nexo.rag.engine import NOT_FOUND, BotProfile, RagEngine
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
    def dot(x, y):
        return sum(i * j for i, j in zip(x, y))

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


class ScoreReranker(BaseNodePostprocessor):
    scores: list[float]

    def _postprocess_nodes(self, nodes, query_bundle=None):
        for n, score in zip(nodes, self.scores + [0.0] * len(nodes)):
            n.score = score
        return sorted(nodes, key=lambda n: n.score, reverse=True)


class CountingLLM:
    def __init__(self, text: str):
        self.text = text
        self.prompts: list[str] = []

    def complete(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.text)

    def stream_complete(self, prompt: str):
        self.prompts.append(prompt)
        yield SimpleNamespace(delta=self.text)


def scored_engine(tmp_path, scores: list[float] | None = None, answer: str | None = None, **kw) -> RagEngine:
    s = Settings(data_dir=tmp_path, embed_provider="hash", llm_provider="extrativo", reranker="none", min_similarity=-1.0,
                 **kw)
    e = RagEngine(s)
    e.ingest("d1", "Manual", "manual.pdf", FIXTURES / "manual-exemplo.pdf")
    if scores is not None:
        e._reranker = ScoreReranker(scores=scores)
        e._reranker_loaded = True
    if answer is not None:
        e._llm = CountingLLM(answer)
        e._llm_loaded = True
    return e


def test_select_keeps_strong_passages_and_drops_far_ones(tmp_path):
    e = scored_engine(tmp_path, [0.9, 0.5, 0.15, 0.05, 0.01])
    nodes, weak = e.select("firmware atualização", None)
    assert weak is False
    assert [round(n.score, 2) for n in nodes] == [0.9, 0.5]


def test_borderline_passages_still_reach_the_model(tmp_path):
    e = scored_engine(tmp_path, [0.05, 0.03, 0.02, 0.001], answer="O LED fica vermelho fixo [1].")
    nodes, weak = e.select("o que significa a luz vermelha", None)
    assert weak is True and len(nodes) == 2
    assert e.retrieve("o que significa a luz vermelha", None) == []
    answer = e.ask("O que significa a luz vermelha?", [], None)
    assert answer.answered is True and len(answer.sources) == 2
    assert len(e._llm.prompts) == 1


def test_unrelated_passages_are_refused_without_calling_the_model(tmp_path):
    e = scored_engine(tmp_path, [0.005, 0.001], answer="não deveria ser chamado")
    nodes, weak = e.select("previsão do tempo para amanhã", None)
    assert nodes == [] and weak is False
    answer = e.ask("Qual a previsão do tempo para amanhã?", [], None)
    assert answer.answered is False and answer.text == NOT_FOUND
    assert e._llm.prompts == []


def test_borderline_passages_without_a_model_are_not_found(tmp_path):
    e = scored_engine(tmp_path, [0.05, 0.03])
    answer = e.ask("O que significa a luz vermelha?", [], None)
    assert answer.answered is False and answer.sources == []


def test_partial_answers_are_kept_and_refusals_use_the_fallback(tmp_path):
    partial = f"Se a atualização falhar, o roteador entra em modo de recuperação [1]. {NOT_FOUND} sobre o prazo de reparo."
    e = scored_engine(tmp_path, [0.9], answer=partial)
    answer = e.ask("O que acontece se a atualização falhar e qual o prazo de reparo?", [], None)
    assert answer.answered is True and answer.text == partial and answer.sources
    e._llm = CountingLLM(f'"{NOT_FOUND}"')
    bot = BotProfile(name="Aurora", fallback="Não sei responder isso. Vou chamar a equipe.")
    answer = e.ask("O que acontece se a atualização falhar?", [], None, bot)
    assert answer.answered is False and answer.text == bot.fallback and answer.sources == []


def test_follow_up_needs_a_single_model_call(tmp_path):
    e = scored_engine(tmp_path, [0.9], answer="Entra em modo de recuperação [1].")
    history = [("user", "Como atualizo o firmware do roteador?"), ("assistant", "Pelo menu Sistema > Atualização [1].")]
    answer = e.ask("E se falhar?", history, None)
    assert len(e._llm.prompts) == 1
    prompt = e._llm.prompts[0]
    assert "Conversa anterior" in prompt and "Usuário: Como atualizo o firmware do roteador?" in prompt
    assert "[1]." not in prompt.split("Trechos:")[0].split("Conversa anterior")[1]
    assert prompt.rstrip().endswith("Pergunta: E se falhar?\nResposta:")
    assert answer.standalone_question == "Como atualizo o firmware do roteador? E se falhar?"


def test_standalone_question_ignores_history(tmp_path):
    e = scored_engine(tmp_path, [0.9], answer="De 0 °C a 40 °C [1].")
    history = [("user", "Como atualizo o firmware?"), ("assistant", "Pelo menu Sistema [1].")]
    answer = e.ask("Qual a temperatura de operação do roteador?", history, None)
    assert "Conversa anterior" not in e._llm.prompts[0]
    assert answer.standalone_question == "Qual a temperatura de operação do roteador?"


def test_small_talk_skips_search_and_model(tmp_path):
    e = scored_engine(tmp_path, [0.9], answer="não deveria ser chamado")
    for text in ("Oi!", "Muito obrigado", "tchau", "O que você faz?"):
        answer = e.ask(text, [], None)
        assert answer.answered is True and answer.sources == []
    assert e._llm.prompts == []
    bot = BotProfile(name="Aurora", greeting="Olá! Sou a Aurora.")
    assert e.ask("Olá, Aurora!", [], None, bot).text == "Olá! Sou a Aurora."
    assert list(e.ask_stream("valeu", [], None, bot))[0].text.startswith("Por nada!")


def test_warm_up_is_throttled_and_reset_by_settings(tmp_path):
    e = scored_engine(tmp_path)
    assert e.warm() is True
    deadline = time.monotonic() + 10
    while e._warming and time.monotonic() < deadline:
        time.sleep(0.02)
    assert e._warmed_at is not None
    assert e.warm() is False
    e.refresh(["llm_model"])
    assert e.warm() is True


def test_warm_up_runs_right_after_boot(tmp_path, monkeypatch):
    import nexo.rag.engine as engine_module
    monkeypatch.setattr(engine_module, "time", SimpleNamespace(monotonic=lambda: 5.0, perf_counter=time.perf_counter))
    e = scored_engine(tmp_path)
    monkeypatch.setattr(e, "_warm_up", lambda: None)
    assert e.warm() is True


def test_ingestion_embeds_outside_the_engine_lock(tmp_path):
    e = scored_engine(tmp_path)
    held: list[bool] = []
    original = e._embed.get_text_embedding_batch

    def spy(texts, **kw):
        if texts:
            held.append(e._lock._is_owned())
        return original(texts, **kw)

    object.__setattr__(e._embed, "get_text_embedding_batch", spy)
    pages, chunks, _ = e.ingest("d2", "Manual 2", "manual2.pdf", FIXTURES / "manual-exemplo.pdf")
    assert pages == 5 and chunks >= 5
    assert held == [False]
    assert e.retrieve("firmware", ["d2"])
