import importlib.machinery
import sys
import types
from types import SimpleNamespace

import pytest
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from pydantic import ValidationError

from nexo.config import Settings
from nexo.rag import providers
from tests.conftest import login


def test_keep_alive_accepts_ollama_durations():
    for value, parsed in (("30m", "30m"), ("1h30m", "1h30m"), ("90s", "90s"), ("-1", -1), ("0", 0), (" 2H ", "2h")):
        s = Settings(ollama_keep_alive=value)
        assert providers.keep_alive(s.ollama_keep_alive) == parsed
    for bad in ("abc", "-5m", "", "30 minutos"):
        with pytest.raises(ValidationError):
            Settings(ollama_keep_alive=bad)


@pytest.mark.parametrize("url, model, effort", [
    ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "low"),
    ("https://api.groq.com/openai/v1", "qwen/qwen3-32b", None),
    ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash", "low"),
    ("https://openrouter.ai/api/v1", "openai/gpt-oss-20b", None),
    ("http://localhost:1234/v1", "gemini-local", None),
])
def test_reasoning_effort_only_where_supported(url, model, effort):
    s = Settings(llm_provider="compativel", openai_base_url=url, llm_model=model)
    assert providers.reasoning_effort(s) == effort


def test_ollama_answers_fast_and_stays_loaded():
    pytest.importorskip("llama_index.llms.ollama")
    llm = providers.build_llm(Settings(llm_provider="ollama", llm_model="qwen3:4b", ollama_keep_alive="45m"))
    assert llm.keep_alive == "45m" and llm.thinking is False
    assert llm._model_kwargs["num_predict"] == providers.MAX_ANSWER_TOKENS
    assert llm._model_kwargs["num_ctx"] == providers.ollama_context(Settings())
    assert providers.build_llm(Settings(llm_provider="ollama", llm_model="gpt-oss:20b")).thinking == "low"


def test_compatible_provider_sends_low_reasoning_effort():
    pytest.importorskip("llama_index.llms.openai_like")
    s = Settings(llm_provider="compativel", openai_base_url="https://api.groq.com/openai/v1", llm_model="openai/gpt-oss-20b")
    assert providers.build_llm(s).additional_kwargs == {"reasoning_effort": "low"}
    s.llm_model = "qwen/qwen3-32b"
    assert providers.build_llm(s).additional_kwargs == {}


def test_preload_only_touches_ollama():
    calls = []
    llm = SimpleNamespace(model="llama3.2:3b", keep_alive="30m", context_window=8192,
                          client=SimpleNamespace(generate=lambda **kw: calls.append(kw)))
    providers.preload(llm, Settings(llm_provider="compativel", openai_base_url="https://api.groq.com/openai/v1"))
    assert calls == []
    providers.preload(llm, Settings(llm_provider="ollama"))
    assert calls == [{"model": "llama3.2:3b", "prompt": "", "keep_alive": "30m", "options": {"num_ctx": 8192}}]


def test_cross_encoder_scores_are_probabilities(monkeypatch):
    created = {}

    class Sigmoid:
        pass

    class FakeCrossEncoder:
        def __init__(self, model, **kw):
            created.update(kw, model=model)

        def predict(self, pairs, **kw):
            return [0.2, 0.97, 0.01][:len(pairs)]

    torch = types.ModuleType("torch")
    torch.nn = SimpleNamespace(Sigmoid=Sigmoid)
    st = types.ModuleType("sentence_transformers")
    st.__spec__ = importlib.machinery.ModuleSpec("sentence_transformers", None)
    st.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", st)
    import llama_index.core.utils as utils
    monkeypatch.setattr(utils, "infer_torch_device", lambda: "cpu")

    reranker = providers.build_reranker(Settings(reranker="huggingface", rerank_model="cross-encoder/teste"))
    assert created["model"] == "cross-encoder/teste" and created["trust_remote_code"] is False
    assert isinstance(created["activation_fn"], Sigmoid)
    nodes = [NodeWithScore(node=TextNode(text=t), score=0.8) for t in ("a", "b", "c")]
    ranked = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle("pergunta"))
    assert [n.node.text for n in ranked] == ["b", "a", "c"]
    assert [n.score for n in ranked] == [0.97, 0.2, 0.01]


def test_warmup_endpoint(client):
    assert client.post("/api/engine/warmup").status_code == 401
    headers = login(client)
    first = client.post("/api/engine/warmup", headers=headers)
    assert first.status_code == 202 and first.json()["started"] is True
    from nexo.config import get_settings
    from nexo.rag.engine import get_engine
    engine = get_engine(get_settings())
    import time
    deadline = time.monotonic() + 10
    while engine._warming and time.monotonic() < deadline:
        time.sleep(0.02)
    assert client.post("/api/engine/warmup", headers=headers).json()["started"] is False


def test_keep_alive_is_adjustable(client):
    headers = login(client)
    items = {i["name"]: i for i in client.get("/api/system/settings", headers=headers).json()["items"]}
    assert items["ollama_keep_alive"]["value"] == "30m" and items["ollama_keep_alive"]["group"] == "Inteligência"
    r = client.put("/api/system/settings", headers=headers, json={"values": {"ollama_keep_alive": "para sempre"}})
    assert r.status_code == 400 and "ollama_keep_alive" in r.json()["fields"]
    r = client.put("/api/system/settings", headers=headers, json={"values": {"ollama_keep_alive": "2h"}})
    assert r.status_code == 200 and r.json()["changed"] == ["ollama_keep_alive"]


def test_agent_with_empty_base_still_greets(client):
    headers = login(client)
    base = client.post("/api/bases", headers=headers, json={"name": "Vazia", "description": "", "color": "#2b4c5a"}).json()
    bot = client.post("/api/bots", headers=headers, json={
        "name": "Aurora", "base_id": base["id"], "suggestions": ["Qual o prazo de troca?"]}).json()
    conv = client.post("/api/conversations", headers=headers, json={"bot_id": bot["id"]}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "Oi!"})
    assert r.status_code == 200
    answer = r.json()["answer"]
    assert answer["answered"] is True and "Aurora" in answer["content"] and "Vazia" in answer["content"]
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "O que você faz?"})
    assert "“Qual o prazo de troca?”" in r.json()["answer"]["content"]
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "Qual o prazo?"})
    assert r.status_code == 409 and r.json()["code"] == "NO_DOCUMENTS"
