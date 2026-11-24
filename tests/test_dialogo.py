import pytest

from nexo.rag.dialogue import (BotProfile, conversation, is_refusal, needs_context, recent, reply, search_query,
                               small_talk)
from nexo.rag.engine import NOT_FOUND

HISTORY = [("user", "Quanto custa o plano Plus?"), ("assistant", "O plano Plus custa R$ 19,90 por mês [1].")]


@pytest.mark.parametrize("text, kind", [
    ("Oi!", "greeting"), ("Olá, tudo bem?", "greeting"), ("Bom dia, Nexo", "greeting"), ("oiii", "greeting"),
    ("Oi, Agente de teste!", "greeting"), ("Muito obrigado!", "thanks"), ("ok, obrigada", "thanks"),
    ("valeu, ajudou muito", "thanks"), ("Entendi", "ack"), ("ok", "ack"), ("Tchau!", "bye"), ("até mais", "bye"),
    ("O que você faz?", "help"), ("ajuda", "help"), ("Quem é você?", "help"), ("menu", "help"),
])
def test_small_talk_is_recognized(text, kind):
    assert small_talk(text, "Agente de teste") == kind


@pytest.mark.parametrize("text", [
    "Oi, qual o horário do suporte?", "Quanto custa o plano Plus?", "Como funciona a garantia?",
    "Obrigado, mas e a garantia estendida?", "Ok, e para resetar o roteador?", "", "   ",
])
def test_real_questions_are_not_small_talk(text):
    assert small_talk(text) is None


def test_replies_use_the_agent_profile():
    bot = BotProfile(name="Aurora", topic="Políticas da loja", suggestions=("Qual o prazo de troca?", "O frete é grátis?"))
    assert "Aurora" in reply("greeting", bot) and "Políticas da loja" in reply("greeting", bot)
    assert reply("greeting", BotProfile(name="Aurora", greeting="Olá! Como posso ajudar?")) == "Olá! Como posso ajudar?"
    assert "“Qual o prazo de troca?” ou “O frete é grátis?”" in reply("help", bot)
    assert reply("thanks", bot).startswith("Por nada!")
    assert reply("bye", None).startswith("Até mais!")
    assert "Nexo" in reply("greeting", None) and "página" in reply("help", None)


@pytest.mark.parametrize("question, expected", [
    ("E o plano Empresarial?", True), ("Quanto custa?", True), ("Ele inclui visita técnica?", True),
    ("Mas e aos sábados?", True), ("Quanto tempo dura a garantia do roteador?", False),
    ("É possível usar o roteador com qualquer operadora?", False),
])
def test_follow_up_detection(question, expected):
    assert needs_context(question, HISTORY) is expected
    assert needs_context(question, []) is False


def test_recent_history_is_short_and_without_citations():
    long = [("user", "pergunta " * 80), ("assistant", "resposta [2] " * 80)] + HISTORY
    out = recent(long, 2)
    assert len(out) == 4
    assert all("[" not in text for _, text in out)
    assert len(out[0][1]) <= 251 and len(out[1][1]) <= 451
    assert recent(long, 0) == []


def test_search_query_and_conversation_block():
    assert search_query("E o Empresarial?", HISTORY) == "Quanto custa o plano Plus? E o Empresarial?"
    assert search_query("Quanto dura a garantia?", []) == "Quanto dura a garantia?"
    block = conversation(recent(HISTORY, 2))
    assert "Usuário: Quanto custa o plano Plus?" in block and "Assistente: O plano Plus custa" in block
    assert conversation([]) == ""


@pytest.mark.parametrize("text, refused", [
    (NOT_FOUND, True), (f'"{NOT_FOUND}"', True), (f"Desculpe, {NOT_FOUND.lower()}", True), ("", True),
    ("Não encontrei essa informação nos documentos.", True), ("Os trechos não informam esse valor.", True),
    (f"O plano Plus custa R$ 19,90 por mês [1]. {NOT_FOUND} sobre descontos anuais.", False),
    ("Os trechos não falam de descontos, mas o plano Plus custa R$ 19,90 [1].", False),
    ("Mantenha o botão RESET pressionado por 15 segundos [1].", False),
])
def test_refusal_detection_keeps_partial_answers(text, refused):
    assert is_refusal(text, NOT_FOUND) is refused
