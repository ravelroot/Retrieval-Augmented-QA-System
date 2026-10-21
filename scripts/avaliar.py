from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from nexo import db
from nexo.config import get_settings
from nexo.rag.engine import get_engine


def load(path: Path) -> list[dict]:
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if "pergunta" not in item or "pagina" not in item:
            raise SystemExit(f"Linha {n}: os campos 'pergunta' e 'pagina' são obrigatórios.")
        items.append(item)
    return items


def resolve(reference: str | None, rows: list[db.DocumentRow]) -> str | None:
    if not reference:
        return None
    for row in rows:
        if reference in (row.id, row.filename, row.title):
            return row.id
    raise SystemExit(f"Documento '{reference}' não encontrado. Use o id, o nome do arquivo ou o título.")


def evaluate(items: list[dict], rows: list[db.DocumentRow], rerank: bool) -> dict:
    engine = get_engine(get_settings())
    hits, rr, details = 0, 0.0, []
    for item in items:
        doc_id = resolve(item.get("documento"), rows)
        nodes = engine.retrieve(item["pergunta"], [doc_id] if doc_id else None, rerank=rerank)
        position = None
        for i, n in enumerate(nodes, start=1):
            same_doc = doc_id is None or n.node.metadata.get("source_id") == doc_id
            if same_doc and int(n.node.metadata.get("page", 0)) == int(item["pagina"]):
                position = i
                break
        if position:
            hits += 1
            rr += 1.0 / position
        details.append((item["pergunta"], item["pagina"], position))
    total = max(len(items), 1)
    return {"hit_rate": hits / total, "mrr": rr / total, "details": details}


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia a recuperação do Nexo com e sem reranking.")
    parser.add_argument("arquivo", type=Path, help="JSONL com pergunta, pagina e, opcionalmente, documento")
    parser.add_argument("--detalhes", action="store_true", help="mostra o resultado de cada pergunta")
    args = parser.parse_args()
    items = load(args.arquivo)
    with db.session() as s:
        rows = list(s.scalars(select(db.DocumentRow).where(db.DocumentRow.status == "READY")))
    if not rows:
        raise SystemExit("Nenhum documento indexado. Envie PDFs pela interface antes de avaliar.")
    settings = get_settings()
    print(f"Perguntas: {len(items)} | top_n: {settings.top_n} | reranker: {settings.reranker}\n")
    print(f"{'Configuração':<22}{'Acerto@n':>10}{'MRR':>10}")
    results = {"Somente vetorial": evaluate(items, rows, rerank=False)}
    if settings.reranker != "none":
        results["Vetorial + reranking"] = evaluate(items, rows, rerank=True)
    for name, r in results.items():
        print(f"{name:<22}{r['hit_rate']:>10.2%}{r['mrr']:>10.3f}")
    if args.detalhes:
        for name, r in results.items():
            print(f"\n{name}")
            for question, page, position in r["details"]:
                print(f"  [{position or '-':>2}] p.{page:<4} {question}")


if __name__ == "__main__":
    main()
