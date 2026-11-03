import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from base import AQUI, RAIZ, VERSAO, gerar_pdf, gravar, localizar_mermaid
import banco
import manual


def main():
    inicio = time.time()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Falta o Playwright: pip install playwright (o Chromium precisa estar instalado).")
    mermaid_js = localizar_mermaid()
    if not mermaid_js:
        sys.exit("Não encontrei o mermaid.min.js. Instale o mermaid-cli (npm i -g @mermaid-js/mermaid-cli) "
                 "ou aponte NEXO_MERMAID_JS para o arquivo.")
    css = (AQUI / "estilo.css").read_text(encoding="utf-8")
    trabalhos = [
        (manual, "Manual-Nexo.pdf", "Nexo · Manual técnico",
         "Instalação, configuração, uso de cada tela, agentes, bases de conhecimento, WhatsApp, integrações, "
         f"arquitetura, banco de dados, API e manutenção do Nexo {VERSAO}, a plataforma de agentes que responde "
         "com base em documentos citando a página.",
         "Nexo, RAG, agentes, bases de conhecimento, WhatsApp, FastAPI, React, manual"),
        (banco, "Banco-de-Dados-Nexo.pdf", "Nexo · Arquitetura do banco de dados",
         "Tabelas, relacionamentos, índices, banco vetorial, contas, bases de conhecimento, agentes, WhatsApp, "
         f"migração automática e consultas do Nexo {VERSAO}.",
         "Nexo, banco de dados, SQLAlchemy, ChromaDB, Qdrant, diagrama de relacionamentos"),
    ]
    with tempfile.TemporaryDirectory(prefix="nexo-pdf-") as temp, sync_playwright() as p:
        navegador = p.chromium.launch()
        for modulo, nome, titulo, assunto, chaves in trabalhos:
            doc = modulo.montar(temp)
            pdf, _ = gerar_pdf(navegador, doc, css, mermaid_js, temp)
            paginas, tamanho = gravar(pdf, [RAIZ / nome, RAIZ / "docs" / nome], titulo, assunto, chaves)
            print(f"{nome}: {paginas} páginas, {tamanho / 1024 / 1024:.1f} MB  (raiz e docs/)")
        navegador.close()
    print(f"Pronto em {time.time() - inicio:.0f} s.")


if __name__ == "__main__":
    main()
