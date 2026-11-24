from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from nexo.rag.hash_embedding import tokens

CITATION = re.compile(r"\[\d{1,2}\]")
WORDS = re.compile(r"\w+")

GREETING = re.compile(r"(oi+e?|ola|opa|hey|hi|hello|alo|salve|e ai|eai|bom dia|boa tarde|boa noite|saudacoes)"
                      r"( (tudo bem|tudo bom|tudo certo|tudo joia|como vai|como vai voce|beleza|blz))?")
THANKS = re.compile(r"((ok|certo|beleza|blz|perfeito|otimo|show|legal|entendi|ah|ta|top|ah ta) )?(muito )?"
                    r"(obrigad[oa]|obg|brigad[oa]|valeu|vlw|grat[oa]|agradeco|thanks|thank you|thx)"
                    r"( (pela ajuda|mesmo|demais|ajudou|ajudou muito))?")
ACK = re.compile(r"ok|okay|certo|beleza|blz|perfeito|otimo|show|legal|entendi|top|ta bom|combinado|ah ta")
BYE = re.compile(r"tchau|xau|ate mais|ate logo|ate amanha|ate breve|falou|flw|bye|adeus")
HELP = re.compile(r"ajuda|help|menu|inicio|o que posso perguntar|o que eu posso perguntar|"
                  r"o que (voce|vc) (faz|sabe|pode fazer|sabe fazer|responde|consegue fazer)|"
                  r"como (voce|vc) funciona|quem e (voce|vc)|quem (voce|vc) e|"
                  r"sobre o que (voce|vc) (sabe|responde|fala)")
KINDS = (("greeting", GREETING), ("thanks", THANKS), ("ack", ACK), ("bye", BYE), ("help", HELP))

FOLLOW_UP_START = {"e", "mas", "então", "entao", "também", "tambem", "além", "alem", "and", "also", "but"}
REFERENCES = {
    "isso", "isto", "esse", "essa", "esses", "essas", "este", "esta", "estes", "estas", "aquele", "aquela",
    "aqueles", "aquelas", "aquilo", "dele", "dela", "deles", "delas", "nele", "nela", "neles", "nelas", "disso",
    "disto", "nisso", "nisto", "daquilo", "desse", "dessa", "desses", "dessas", "deste", "desta", "destes",
    "destas", "nesse", "nessa", "neste", "nesta", "ele", "ela", "eles", "elas", "mesmo", "mesma", "anterior",
    "acima", "it", "that", "this", "those", "these", "them",
}
REFUSAL_START = ("nao encontrei", "nao ha informac", "os trechos nao", "os documentos nao", "nao consta")

USER_CHARS = 250
ANSWER_CHARS = 450
QUERY_CHARS = 300


@dataclass
class BotProfile:
    name: str
    instructions: str | None = None
    greeting: str | None = None
    fallback: str | None = None
    topic: str | None = None
    suggestions: tuple[str, ...] = field(default_factory=tuple)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def small_talk(text: str, name: str | None = None) -> str | None:
    clean = fold(text)
    if not clean or len(clean) > 60:
        return None
    for alias in {"nexo", fold(name or "")} - {""}:
        clean = " ".join(re.sub(rf"(^| ){re.escape(alias)}( |$)", " ", clean).split())
    if not clean:
        return None
    return next((kind for kind, pattern in KINDS if pattern.fullmatch(clean)), None)


def is_salutation(text: str) -> bool:
    return small_talk(text) == "greeting"


def _quote(items: tuple[str, ...]) -> str:
    return " ou ".join(f"“{s.strip()}”" for s in items[:2] if s.strip())


def reply(kind: str, bot: BotProfile | None) -> str:
    if kind in ("thanks", "ack"):
        return ("Por nada!" if kind == "thanks" else "Combinado!") + " Se tiver outra dúvida, é só perguntar."
    if kind == "bye":
        return "Até mais! Quando precisar, é só chamar."
    if bot is None:
        if kind == "greeting":
            return "Olá! Sou o Nexo. Pergunte o que precisar sobre os documentos e eu respondo citando o trecho e a página."
        return ("Eu respondo dúvidas com base nos documentos enviados ao Nexo e mostro o trecho e a página de onde tirei "
                "cada informação. Pergunte de forma direta, citando o assunto, por exemplo: “Como faço para…?” ou "
                "“Qual o prazo de…?”.")
    about = f"os documentos da base “{bot.topic}”" if bot.topic else "os documentos que eu conheço"
    if kind == "greeting":
        return bot.greeting or f"Olá! Sou {bot.name}. Pergunte o que precisar sobre {about}."
    examples = _quote(bot.suggestions)
    tip = f" Você pode perguntar, por exemplo: {examples}." if examples else " Pergunte de forma direta, citando o assunto."
    return f"Eu respondo dúvidas com base em {about}, sempre a partir do que está escrito neles.{tip}"


def needs_context(question: str, history: list[tuple[str, str]]) -> bool:
    if not any(role == "user" for role, _ in history):
        return False
    words = WORDS.findall(question.lower())
    if not words:
        return False
    return len(tokens(question)) <= 2 or words[0] in FOLLOW_UP_START or bool(REFERENCES & set(words))


def recent(history: list[tuple[str, str]], turns: int) -> list[tuple[str, str]]:
    if turns <= 0:
        return []
    out = []
    for role, text in history[-2 * turns:]:
        text = " ".join(CITATION.sub("", text).split())
        limit = USER_CHARS if role == "user" else ANSWER_CHARS
        out.append((role, text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"))
    return out


def search_query(question: str, context: list[tuple[str, str]]) -> str:
    previous = next((text for role, text in reversed(context) if role == "user"), "")
    return f"{previous[:QUERY_CHARS]} {question}".strip() if previous else question


def conversation(context: list[tuple[str, str]]) -> str:
    if not context:
        return ""
    lines = "\n".join(f"{'Usuário' if role == 'user' else 'Assistente'}: {text}" for role, text in context)
    return f"\nConversa anterior, só para entender a pergunta:\n{lines}\n"


def is_refusal(text: str, phrase: str) -> bool:
    folded = fold(text)
    if not folded:
        return True
    key = fold(phrase)
    if key and key in folded:
        return len(folded.replace(key, " ").strip()) < 40
    return folded.startswith(REFUSAL_START) and len(folded) < 160 and not CITATION.search(text)
