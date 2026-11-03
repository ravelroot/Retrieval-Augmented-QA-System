import glob
import html
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
IMAGENS = RAIZ / "docs" / "images"
VERSAO = "2.2.0"
DATA = "Novembro de 2026"
AUTOR = "Erik Pimenta"
PRODUTO = "Nexo"

LARGURA_UTIL_MM = 170

TEMA_MERMAID = {
    "startOnLoad": False,
    "theme": "base",
    "fontFamily": "Instrument Sans",
    "themeVariables": {
        "fontFamily": "Instrument Sans", "fontSize": "13px",
        "background": "#FFFFFF", "primaryColor": "#FFFFFF", "primaryTextColor": "#000000",
        "primaryBorderColor": "#BAB7B6", "secondaryColor": "#F5F4F4", "tertiaryColor": "#F5F4F4",
        "lineColor": "#4D4B4B", "textColor": "#000000", "mainBkg": "#FFFFFF", "nodeBorder": "#BAB7B6",
        "clusterBkg": "#F5F4F4", "clusterBorder": "#DCDAD9", "edgeLabelBackground": "#FFFFFF",
        "actorBkg": "#000000", "actorBorder": "#000000", "actorTextColor": "#FFFFFF", "actorLineColor": "#BAB7B6",
        "signalColor": "#000000", "signalTextColor": "#000000", "labelBoxBkgColor": "#F5F4F4",
        "labelBoxBorderColor": "#000000", "labelTextColor": "#000000", "loopTextColor": "#000000",
        "noteBkgColor": "#F5F4F4", "noteBorderColor": "#DCDAD9", "noteTextColor": "#000000",
        "activationBkgColor": "#F5F4F4", "activationBorderColor": "#000000", "sequenceNumberColor": "#FFFFFF",
        "attributeBackgroundColorOdd": "#FFFFFF", "attributeBackgroundColorEven": "#FAFAFA",
        "rowOdd": "#FFFFFF", "rowEven": "#FAFAFA",
        "stateBkg": "#FFFFFF", "stateLabelColor": "#000000", "compositeBackground": "#F5F4F4",
        "transitionColor": "#4D4B4B", "transitionLabelColor": "#000000", "specialStateColor": "#000000",
        "innerEndBackground": "#000000",
    },
    "er": {"layoutDirection": "TB", "entityPadding": 10, "minEntityWidth": 90, "fontSize": 12, "useMaxWidth": False},
    "sequence": {"useMaxWidth": False, "mirrorActors": False, "actorMargin": 40, "messageMargin": 28,
                 "boxMargin": 8, "noteMargin": 8, "messageFontSize": 12, "actorFontSize": 13, "noteFontSize": 12},
    "flowchart": {"useMaxWidth": False, "curve": "basis", "padding": 12, "nodeSpacing": 30, "rankSpacing": 34,
                  "htmlLabels": True},
    "state": {"useMaxWidth": False},
}


def md(texto):
    s = html.escape(texto, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = s.replace("[[novo]]", '<span class="novo">Novo</span>')
    return s


def localizar_mermaid():
    candidatos = [os.environ.get("NEXO_MERMAID_JS", "")]
    try:
        raiz_npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=15).stdout.strip()
        if raiz_npm:
            candidatos += [f"{raiz_npm}/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js",
                           f"{raiz_npm}/mermaid/dist/mermaid.min.js"]
    except Exception:
        pass
    mmdc = shutil.which("mmdc")
    if mmdc:
        base = Path(os.path.realpath(mmdc)).parent
        candidatos += glob.glob(str(base / ".." / "**" / "mermaid" / "dist" / "mermaid.min.js"), recursive=True)[:1]
    candidatos += ["/opt/npm-tools/node_modules/mermaid/dist/mermaid.min.js",
                   str(RAIZ / "frontend" / "node_modules" / "mermaid" / "dist" / "mermaid.min.js")]
    for c in candidatos:
        if c and Path(c).is_file():
            return Path(c).resolve()
    return None


def logo_svg():
    arq = IMAGENS / "logo.svg"
    if not arq.is_file():
        return ""
    s = arq.read_text(encoding="utf-8")
    s = re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
    s = re.sub(r'<rect width="500" height="500"[^>]*/>', "", s)
    s = re.sub(r'\s(width|height)="500"', "", s, count=2)
    s = s.replace('viewBox="0 0 500 500"', 'viewBox="140 140 220 220"')
    return s


class Documento:
    def __init__(self, cabecalho, temp):
        self.cabecalho = cabecalho
        self.temp = Path(temp)
        self.partes = []
        self.sumario = []
        self.cap = 0
        self.sec = 0
        self.fig = 0
        self.n = 0
        self.diagramas = []

    def _id(self):
        self.n += 1
        return f"s{self.n}"

    def raw(self, h):
        self.partes.append(h)

    def capa(self, titulo, subtitulo):
        self.raw(f"""
<section class="capa">
  <div class="logo">{logo_svg()}</div>
  <div class="meio">
    <div class="marca">{PRODUTO}</div>
    <div class="titulo">{md(titulo)}</div>
    <div class="subtitulo">{md(subtitulo)}</div>
  </div>
  <div class="rodape"><span><b>Versão {VERSAO}</b>{DATA}</span><span>Copyright (©) 2026 {AUTOR}</span></div>
</section>""")

    def lugar_do_sumario(self):
        self.raw("<!--SUMARIO-->")

    def capitulo(self, titulo, abertura=None):
        self.cap += 1
        self.sec = 0
        self.fig = 0
        i = self._id()
        num = f"{self.cap:02d}"
        self.sumario.append((1, i, titulo, num))
        ab = f'<p class="abertura">{md(abertura)}</p>' if abertura else ""
        self.raw(f'<section class="capitulo"><div class="numero">{num}</div>'
                 f'<h1 id="{i}">{md(titulo)}</h1>{ab}</section>')

    def secao(self, titulo, quebra=False, novo=False):
        self.sec += 1
        i = self._id()
        num = f"{self.cap}.{self.sec}"
        self.sumario.append((2, i, titulo, num))
        cls = ' class="quebra"' if quebra else ""
        selo = '<span class="novo">Novo</span>' if novo else ""
        self.raw(f'<h2 id="{i}"{cls}><span class="n">{num}</span><span>{md(titulo)}{selo}</span></h2>')

    def sub(self, titulo):
        self.raw(f"<h3>{md(titulo)}</h3>")

    def p(self, texto, cls=""):
        self.raw(f'<p class="{cls}">{md(texto)}</p>' if cls else f"<p>{md(texto)}</p>")

    def lista(self, itens):
        self.raw('<ul class="lista">' + "".join(f"<li>{md(x)}</li>" for x in itens) + "</ul>")

    def passos(self, itens):
        self.raw('<ol class="passos">' + "".join(f"<li>{md(x)}</li>" for x in itens) + "</ol>")

    def codigo(self, texto, rotulo=None):
        r = f'<div class="rotulo-cod">{html.escape(rotulo)}</div>' if rotulo else ""
        self.raw(f"{r}<pre><code>{html.escape(texto.strip(chr(10)))}</code></pre>")

    def nota(self, titulo, texto, alerta=False):
        t = f'<span class="t">{md(titulo)}</span> ' if titulo else ""
        self.raw(f'<div class="nota{" alerta" if alerta else ""}"><p>{t}{md(texto)}</p></div>')

    def cartoes(self, itens):
        blocos = []
        for titulo, etiqueta, texto in itens:
            e = f'<span class="e">{md(etiqueta)}</span>' if etiqueta else ""
            blocos.append(f'<div><span class="t">{md(titulo)}</span>{e}<p>{md(texto)}</p></div>')
        self.raw('<div class="cartoes">' + "".join(blocos) + "</div>")

    def tabela(self, cab, linhas, larguras=None, cls="", alinhar=None):
        alinhar = alinhar or {}
        col = ""
        if larguras:
            col = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in larguras) + "</colgroup>"
        th = "".join(f'<th class="{alinhar.get(k, "")}">{md(c)}</th>' for k, c in enumerate(cab))
        corpo = []
        for linha in linhas:
            if isinstance(linha, str):
                corpo.append(f'<tr class="grupo"><td colspan="{len(cab)}">{md(linha)}</td></tr>')
                continue
            tds = []
            for k, c in enumerate(linha):
                conteudo = c[4:] if isinstance(c, str) and c.startswith("RAW:") else md(str(c))
                tds.append(f'<td class="{alinhar.get(k, "")}">{conteudo}</td>')
            corpo.append("<tr>" + "".join(tds) + "</tr>")
        self.raw(f'<div class="tabela"><table class="{cls}">{col}<thead><tr>{th}</tr></thead>'
                 f'<tbody>{"".join(corpo)}</tbody></table></div>')

    def _legenda(self, legenda):
        self.fig += 1
        return f"<figcaption><b>Figura {self.cap}.{self.fig}</b>{md(legenda)}</figcaption>"

    def tela(self, arquivo, legenda, largura_mm=LARGURA_UTIL_MM, altura_max_mm=150, junto=False):
        self.raw(self._figura(arquivo, legenda, largura_mm, altura_max_mm, junto))

    def lado(self, paragrafos, arquivo, legenda, largura_mm=46, altura_max_mm=110):
        texto = "".join(f"<p>{md(x)}</p>" for x in paragrafos)
        self.raw(f'<div class="lado"><div class="texto">{texto}</div>'
                 f'{self._figura(arquivo, legenda, largura_mm, altura_max_mm, False, largura_mm)}</div>')

    def _figura(self, arquivo, legenda, largura_mm, altura_max_mm, junto=False, largura_fig=None):
        orig = IMAGENS / arquivo
        cls = ' class="junto"' if junto else ""
        estilo = f' style="width:{largura_fig}mm"' if largura_fig else ""
        cap = self._legenda(legenda)
        if not orig.is_file():
            return (f'<figure{cls}{estilo}><div style="width:{largura_mm}mm;height:40mm;border:.8pt dashed #BAB7B6;'
                    f'border-radius:4px"></div>{cap}</figure>')
        from PIL import Image
        im = Image.open(orig)
        im.load()
        w, h = im.size
        if w > 1800:
            im = im.resize((1800, round(h * 1800 / w)), Image.LANCZOS)
            w, h = im.size
        destino = self.temp / (Path(arquivo).stem + ".jpg")
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fundo.paste(im, mask=im.getchannel("A"))
        else:
            fundo.paste(im.convert("RGB"))
        fundo.save(destino, "JPEG", quality=86, optimize=True)
        larg = largura_mm
        alt = larg * h / w
        if alt > altura_max_mm:
            alt = altura_max_mm
            larg = alt * w / h
        return (f'<figure{cls}{estilo}><img class="tela" src="{destino.as_uri()}" '
                f'style="width:{larg:.1f}mm;height:{alt:.1f}mm" alt="">{cap}</figure>')

    def diagrama(self, fonte, legenda, largura_mm=LARGURA_UTIL_MM - 7, altura_max_mm=190, escala_max=1.0):
        k = len(self.diagramas)
        self.diagramas.append(fonte)
        self.raw(f'<figure class="bloco-diagrama"><div class="diagrama" data-w="{largura_mm}" data-h="{altura_max_mm}" '
                 f'data-s="{escala_max}"><pre class="mermaid" id="mm{k}">{html.escape(fonte)}</pre></div>'
                 f'{self._legenda(legenda)}</figure>')

    def html_final(self, paginas, css):
        itens = []
        for nivel, i, titulo, num in self.sumario:
            pg = paginas.get(i, "")
            itens.append(f'<li class="n{nivel}"><a href="#{i}"><span class="num">{num}</span><span class="t">{md(titulo)}</span>'
                         f'<span class="pg">{pg}</span></a></li>')
        sumario = f'<section class="sumario"><h1>Sumário</h1><ol>{"".join(itens)}</ol></section>'
        corpo = "\n".join(self.partes).replace("<!--SUMARIO-->", sumario)
        return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><base href="{AQUI.as_uri()}/">'
                f"<style>{css}</style></head><body>{corpo}</body></html>")


JS_DIAGRAMAS = """
async (config) => {
  await document.fonts.ready;
  for (const f of ['400 13px "Instrument Sans"', '600 13px "Instrument Sans"', '500 20px "Bricolage"', '300 20px "Bricolage"', '12px "Plex Mono"'])
    await document.fonts.load(f);
  if (!document.querySelector('pre.mermaid')) return 'ok';
  mermaid.initialize(config);
  await mermaid.run({ querySelector: 'pre.mermaid' });
  const mm = 96 / 25.4;
  for (const fig of document.querySelectorAll('div.diagrama')) {
    const svg = fig.querySelector('svg');
    if (!svg) continue;
    const vb = svg.viewBox.baseVal;
    const maxW = parseFloat(fig.dataset.w) * mm, maxH = parseFloat(fig.dataset.h) * mm;
    const s = Math.min(parseFloat(fig.dataset.s || '1'), maxW / vb.width, maxH / vb.height);
    svg.removeAttribute('style');
    svg.setAttribute('width', (vb.width * s).toFixed(1));
    svg.setAttribute('height', (vb.height * s).toFixed(1));
  }
  return 'ok';
}
"""


def gerar_pdf(navegador, doc, css_modelo, mermaid_js, saida_temp):
    from pypdf import PdfReader

    css = css_modelo.replace("{{CABECALHO}}", doc.cabecalho).replace("{{VERSAO}}", f"Versão {VERSAO}")
    paginas = {i: "00" for _, i, _, _ in doc.sumario}
    pdf = None
    for passagem in (1, 2):
        conteudo = doc.html_final(paginas, css)
        if mermaid_js:
            conteudo = conteudo.replace("</head>", f'<script src="{mermaid_js.as_uri()}"></script>'
                                        f'<script>mermaid.initialize({json.dumps(TEMA_MERMAID)});</script></head>')
        arq = Path(saida_temp) / f"{doc.cabecalho.replace(' ', '-')}-{passagem}.html"
        arq.write_text(conteudo, encoding="utf-8")
        pagina = navegador.new_page()
        pagina.goto(arq.as_uri(), wait_until="load")
        pagina.evaluate(JS_DIAGRAMAS, TEMA_MERMAID)
        opcoes = dict(format="A4", print_background=True, prefer_css_page_size=True,
                      margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        try:
            pdf = pagina.pdf(**opcoes, outline=True, tagged=True)
        except TypeError:
            pdf = pagina.pdf(**opcoes)
        pagina.close()
        if passagem == 1:
            leitor = PdfReader(io.BytesIO(pdf))
            achados = {}
            for nome, d in leitor.named_destinations.items():
                try:
                    achados[str(nome).lstrip("/")] = leitor.get_destination_page_number(d) + 1
                except Exception:
                    pass
            faltando = [i for i in paginas if i not in achados]
            if faltando:
                raise RuntimeError(f"Não encontrei a página destes títulos: {faltando[:5]}")
            paginas = {i: str(achados[i]) for i in paginas}
    return pdf, paginas


def gravar(pdf_bytes, destinos, titulo, assunto, palavras):
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf_bytes)))
    escritor.add_metadata({"/Title": titulo, "/Subject": assunto, "/Author": AUTOR, "/Creator": PRODUTO,
                           "/Producer": PRODUTO, "/Keywords": palavras})
    buf = io.BytesIO()
    escritor.write(buf)
    dados = buf.getvalue()
    for d in destinos:
        Path(d).write_bytes(dados)
    return len(PdfReader(io.BytesIO(dados)).pages), len(dados)
