# Gerador dos PDFs da documentação

Gera os dois PDFs do Nexo com a identidade visual da interface:

- `Manual-Nexo.pdf` (manual técnico)
- `Banco-de-Dados-Nexo.pdf` (arquitetura do banco de dados)

Cada um é gravado em duas cópias iguais: na raiz do projeto e em `docs/`.

## Como rodar

Na raiz do projeto:

```bash
python3 scripts/docs/gerar_pdfs.py
```

Leva poucos segundos. Precisa de:

1. Python 3 com `playwright` (Chromium já instalado), `pypdf` e `Pillow`.
2. O `mermaid.min.js`, que vem com o mermaid-cli (`npm i -g @mermaid-js/mermaid-cli`). O script procura sozinho; se não achar, aponte `NEXO_MERMAID_JS` para o arquivo.

## Como funciona

| Arquivo | Papel |
|---|---|
| `gerar_pdfs.py` | Ponto de entrada: monta os dois documentos, gera os PDFs e grava os metadados |
| `manual.py` | Texto do manual, capítulo por capítulo |
| `banco.py` | Texto do PDF do banco e o diagrama de relacionamentos, que o manual também usa |
| `base.py` | Versão, data, marcação (títulos, tabelas, passos, cartões, código, avisos, telas e diagramas) e geração com o Chromium |
| `estilo.css` | Identidade visual: cores, tipografia, capa, sumário, cabeçalho e rodapé |
| `fontes/` | Bricolage Grotesque, Instrument Sans e IBM Plex Mono, embutidas no PDF |

- A versão e a data ficam em `base.py` (`VERSAO` e `DATA`) e aparecem na capa, no cabeçalho, nos textos e nos metadados.
- O Sumário é feito em duas passagens: a primeira descobre a página de cada título, a segunda escreve os números.
- Os diagramas são desenhados com Mermaid dentro da própria página, com as mesmas fontes, e saem em vetor.
- As capturas vêm de `docs/images/tela-*.png`, convertidas para JPEG. A logo da capa vem de `docs/images/logo.svg`.
- O número de testes do capítulo 10 do manual é contado em `tests/` a cada geração.
- Para mudar o texto, edite `manual.py` ou `banco.py`. Use `` `código` ``, `**negrito**` e `[[novo]]` (selo Novo) dentro dos textos.
