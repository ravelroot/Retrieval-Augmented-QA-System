from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding

WORD_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a o as os um uma uns umas de do da dos das e em no na nos nas por para com sem que se ao aos à às é ser "
    "como mais mas ou sua seu suas seus este esta isso isto esse essa qual quais quando onde the of and to in "
    "is are for on with by an be this that it as at from or".split()
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize(text)) if len(w) > 1 and w not in STOPWORDS]


class HashEmbedding(BaseEmbedding):
    dimensions: int = 768
    _cache: dict = PrivateAttr(default_factory=dict)

    @classmethod
    def class_name(cls) -> str:
        return "NexoHashEmbedding"

    def _vector(self, text: str) -> list[float]:
        words = tokens(text)
        feats = Counter(words)
        feats.update(f"{a}_{b}" for a, b in zip(words, words[1:]))
        for w in words:
            if len(w) > 4:
                feats.update(w[i:i + 4] for i in range(len(w) - 3))
        vec = [0.0] * self.dimensions
        for feat, count in feats.items():
            h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dimensions
            sign = 1.0 if h[4] & 1 else -1.0
            weight = 1.0 + math.log(count)
            if "_" in feat:
                weight *= 0.7
            elif len(feat) == 4 and feat not in words:
                weight *= 0.35
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)
