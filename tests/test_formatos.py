from __future__ import annotations

import io
import zipfile

import pytest

from nexo import knowledge
from nexo.knowledge import ReadError
from tests.conftest import login

DC = "http://purl.org/dc/elements/1.1/"
DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRESENTATION = "http://schemas.openxmlformats.org/presentationml/2006/main"
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ODF_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
ODF_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
LONG = "Parágrafo longo sobre faróis, marés e navegação costeira. "
EPUB_QUERY = "faroleiro querosene porão de pedra"
MEDIA = {
    "epub": "application/epub+zip",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "odt": "application/vnd.oasis.opendocument.text",
}


def build_zip(members: dict[str, str | bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z:
        for name, content in members.items():
            z.writestr(name, content)
    return buffer.getvalue()


def core_xml(title: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            f'xmlns:dc="{DC}"><dc:title>{title}</dc:title></cp:coreProperties>')


def xhtml(body: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head>'
            '<title>Título interno</title><style>p { color: red }</style></head>'
            f'<body>{body}<script>alerta()</script></body></html>')


def epub_bytes(title: str = "O Farol de Itaipu") -> bytes:
    long_chapter = "<h1>Capítulo 1</h1>" + "".join(f"<p>{LONG * 13}Trecho {i}.</p>" for i in range(1, 7))
    container = ('<?xml version="1.0"?><container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')
    opf = ('<?xml version="1.0" encoding="UTF-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           f'unique-identifier="uid"><metadata xmlns:dc="{DC}"><dc:identifier id="uid">nexo-teste</dc:identifier>'
           f'<dc:title>{title}</dc:title><dc:language>pt-BR</dc:language></metadata><manifest>'
           '<item id="cap2" href="Texto/capitulo%202.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="cap1" href="Texto/capitulo1.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="sumiu" href="Texto/nao-existe.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="css" href="estilo.css" media-type="text/css"/>'
           '</manifest><spine><itemref idref="cap1"/><itemref idref="sumiu"/><itemref idref="fantasma"/>'
           '<itemref idref="css"/><itemref idref="cap2"/></spine></package>')
    return build_zip({
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": container,
        "OEBPS/content.opf": opf,
        "OEBPS/estilo.css": "p { margin: 0 }",
        "OEBPS/Texto/capitulo 2.xhtml": xhtml("<h1>Capítulo 2</h1><p>O faroleiro Bento guardava o querosene no "
                                              "porão de pedra.</p>"),
        "OEBPS/Texto/capitulo1.xhtml": xhtml(long_chapter),
    })


def slide_xml(paragraphs: list[list[str]]) -> str:
    body = "".join("<a:p>" + "".join(f"<a:r><a:t>{run}</a:t></a:r>" for run in runs) + "<a:endParaRPr/></a:p>"
                   for runs in paragraphs)
    return ('<?xml version="1.0" encoding="UTF-8"?><p:sld '
            f'xmlns:p="{PRESENTATION}" xmlns:a="{DRAWING}">'
            f'<p:cSld><p:spTree><p:sp><p:txBody>{body}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>')


def pptx_bytes(title: str = "Treinamento Comercial") -> bytes:
    return build_zip({
        "[Content_Types].xml": "<Types/>",
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{PRESENTATION}"/>',
        "ppt/slides/slide10.xml": slide_xml([["Encerramento e perguntas"]]),
        "ppt/slides/slide2.xml": slide_xml([[]]),
        "ppt/slides/slide1.xml": slide_xml([["Treinamento ", "de vendas"], ["Módulo   inicial"]]),
        "ppt/slides/slide3.xml": slide_xml([["Metas do trimestre"]]),
        "ppt/slides/_rels/slide1.xml.rels": "<Relationships/>",
        "docProps/core.xml": core_xml(title),
    })


def cell(ref: str, value: str, kind: str | None = None) -> str:
    if kind == "inlineStr":
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    attribute = f' t="{kind}"' if kind else ""
    return f'<c r="{ref}"{attribute}><v>{value}</v></c>'


def sheet_xml(rows: list[tuple[int, list[str]]]) -> str:
    body = "".join(f'<row r="{number}">{"".join(cells)}</row>' for number, cells in rows)
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{SHEET}"><sheetData>{body}</sheetData></worksheet>'


def xlsx_bytes() -> bytes:
    workbook = (f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{SHEET}" xmlns:r="{RELS}"><sheets>'
                '<sheet name="Vendas" sheetId="1" r:id="rId2"/><sheet name="Estoque" sheetId="2" r:id="rId1"/>'
                '<sheet name="Resumo" sheetId="3" r:id="rId9"/></sheets></workbook>')
    relationships = ('<?xml version="1.0" encoding="UTF-8"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     f'<Relationship Id="rId1" Type="{RELS}/worksheet" Target="worksheets/sheet1.xml"/>'
                     f'<Relationship Id="rId2" Type="{RELS}/worksheet" Target="worksheets/sheet2.xml"/>'
                     f'<Relationship Id="rId3" Type="{RELS}/sharedStrings" Target="sharedStrings.xml"/>'
                     '</Relationships>')
    shared = (f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{SHEET}" count="6" uniqueCount="6">'
              '<si><t>produto</t></si><si><t>preco</t></si><si><t>ativo</t></si><si><t>Caneca térmica</t></si>'
              '<si><r><t xml:space="preserve">Garrafa </t></r><r><rPr><b/></rPr><t>inox</t></r></si>'
              '<si><t>quantidade</t><rPh sb="0" eb="1"><t>FONETICA</t></rPh></si></sst>')
    vendas = sheet_xml([
        (1, [cell("A1", "0", "s"), cell("B1", "1", "s"), cell("C1", "2", "s")]),
        (2, [cell("A2", "3", "s"), cell("B2", "89.9"), cell("C2", "1", "b")]),
        (3, []),
        (4, [cell("A4", "4", "s"), cell("B4", "129"), cell("C4", "0", "b"), cell("E4", "promoção", "inlineStr")]),
    ])
    estoque = sheet_xml([(1, [cell("A1", "5", "s"), cell("B1", "local", "inlineStr")])] + [
        (n, [cell(f"A{n}", str(n * 10)), cell(f"B{n}", f"Galpão {n}", "inlineStr")]) for n in range(2, 47)])
    resumo = sheet_xml([
        (1, [cell("A1", "total", "inlineStr")]),
        (2, [cell("A2", "0.30000000000000004"), '<c r="B2" t="str"><f>CONCAT("o","k")</f><v>ok</v></c>']),
    ])
    return build_zip({
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": relationships,
        "xl/sharedStrings.xml": shared,
        "xl/worksheets/sheet1.xml": estoque,
        "xl/worksheets/sheet2.xml": vendas,
        "xl/worksheets/sheet3.xml": resumo,
    })


def odt_bytes(title: str = "Regulamento da Biblioteca") -> bytes:
    body = "".join([
        '<text:h text:outline-level="1">Regulamento   interno</text:h>',
        '<text:p>Horário de <text:span>atendimento:<text:s text:c="3"/>das 8h</text:span><text:tab/>às 18h.</text:p>',
        '<text:p>Primeira linha<text:line-break/>Segunda linha</text:p>',
        '<text:tracked-changes><text:changed-region text:id="c1"><text:deletion><text:p>Trecho apagado</text:p>'
        '</text:deletion></text:changed-region></text:tracked-changes>',
        '<text:p>Prazo de 30 dias<office:annotation><text:p>Comentário interno</text:p></office:annotation>'
        ' corridos.</text:p>',
        '<text:p>Legenda<draw:frame><draw:text-box><text:p>Texto na caixa</text:p></draw:text-box></draw:frame>'
        '</text:p>',
        '<table:table><table:table-row><table:table-cell><text:p>Célula A</text:p></table:table-cell>'
        '</table:table-row></table:table>',
        '<text:p/>',
    ])
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               f'<office:document-content xmlns:office="{ODF_OFFICE}" xmlns:text="{ODF_TEXT}" '
               'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" office:version="1.3">'
               f'<office:body>\n  <office:text>\n    {body}\n  </office:text>\n</office:body>'
               '</office:document-content>')
    meta = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta xmlns:office="{ODF_OFFICE}" '
            f'xmlns:dc="{DC}"><office:meta><dc:title>{title}</dc:title></office:meta></office:document-meta>')
    return build_zip({"mimetype": "application/vnd.oasis.opendocument.text", "content.xml": content,
                      "meta.xml": meta})


def test_extensions_and_signatures():
    assert knowledge.FILE_EXTENSIONS == ("pdf", "docx", "epub", "pptx", "xlsx", "odt", "txt", "md", "csv", "json",
                                         "html", "htm")
    for extension in ("docx", "epub", "pptx", "xlsx", "odt"):
        assert knowledge.looks_valid(b"PK\x03\x04resto", extension)
        assert not knowledge.looks_valid(b"%PDF-1.4", extension)
        assert knowledge.kind_of(extension) == "file"


def test_epub_follows_spine_and_numbers_parts_across_book():
    content = knowledge.read_epub(epub_bytes())
    assert content.title == "O Farol de Itaipu"
    assert [number for number, _ in content.parts] == [1, 2, 3]
    assert content.parts[0][1].startswith("Capítulo 1\n\n")
    assert "Trecho 1." in content.parts[0][1] and "Trecho 6." in content.parts[1][1]
    assert content.parts[2][1] == "Capítulo 2\n\nO faroleiro Bento guardava o querosene no porão de pedra."
    text = "\n".join(part for _, part in content.parts)
    assert "Título interno" not in text and "alerta" not in text and "color" not in text and "margin" not in text


def test_epub_without_parts_or_with_missing_package():
    container = ('<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
    with pytest.raises(ReadError, match="EPUB"):
        knowledge.read_epub(build_zip({"META-INF/container.xml": container}))
    opf = ('<package xmlns="http://www.idpf.org/2007/opf"><metadata/><manifest/><spine>'
           '<itemref idref="nada"/></spine></package>')
    empty = knowledge.read_epub(build_zip({"META-INF/container.xml": container, "OEBPS/content.opf": opf}))
    assert empty.title is None and empty.parts == []


def test_pptx_orders_slides_numerically_and_keeps_slide_numbers():
    content = knowledge.read_pptx(pptx_bytes())
    assert content.title == "Treinamento Comercial"
    assert content.parts == [(1, "Treinamento de vendas\nMódulo inicial"), (3, "Metas do trimestre"),
                             (10, "Encerramento e perguntas")]


def test_xlsx_reads_shared_strings_types_and_sheet_names():
    content = knowledge.read_xlsx(xlsx_bytes())
    assert content.title is None
    assert [number for number, _ in content.parts] == [1, 2]
    first, second = (part.split("\n") for _, part in content.parts)
    assert len(first) == knowledge.CSV_ROWS and len(second) == 8
    assert first[:3] == [
        "Planilha Vendas, linha 2. produto: Caneca térmica; preco: 89.9; ativo: VERDADEIRO.",
        "Planilha Vendas, linha 4. produto: Garrafa inox; preco: 129; ativo: FALSO; coluna 5: promoção.",
        "Planilha Estoque, linha 2. quantidade: 20; local: Galpão 2.",
    ]
    assert second[-2:] == ["Planilha Estoque, linha 46. quantidade: 460; local: Galpão 46.",
                           "Planilha Resumo, linha 2. total: 0.3; coluna 2: ok."]
    assert all("FONETICA" not in part for _, part in content.parts)


def test_xlsx_without_shared_strings_or_relationships_uses_sheet_fallback():
    workbook = f'<workbook xmlns="{SHEET}"><sheets><sheet name="Única" sheetId="7"/></sheets></workbook>'
    sheet = sheet_xml([(1, [cell("A1", "nome", "inlineStr")])])
    content = knowledge.read_xlsx(build_zip({"xl/workbook.xml": workbook, "xl/worksheets/sheet1.xml": sheet}))
    assert content.parts == [(1, "Planilha Única. Colunas: nome.")]


def test_odt_reads_headings_paragraphs_and_inline_marks():
    content = knowledge.read_odt(odt_bytes())
    assert content.title == "Regulamento da Biblioteca"
    assert content.parts == [(1, "Regulamento interno\n\nHorário de atendimento: das 8h às 18h.\n\n"
                                 "Primeira linha\nSegunda linha\n\nPrazo de 30 dias corridos.\n\nLegenda\n\n"
                                 "Texto na caixa\n\nCélula A")]


def test_csv_lines_are_unchanged():
    content = knowledge.read_csv("produto;preco\nCaneca;89,90\n\nGarrafa;129\n".encode())
    assert content.parts == [(1, "Linha 2. produto: Caneca; preco: 89,90.\nLinha 3. produto: Garrafa; preco: 129.")]


@pytest.mark.parametrize("extension,data,title", [
    ("epub", epub_bytes(), "O Farol de Itaipu"),
    ("pptx", pptx_bytes(), "Treinamento Comercial"),
    ("xlsx", xlsx_bytes(), None),
    ("odt", odt_bytes(), "Regulamento da Biblioteca"),
])
def test_read_file_dispatches_new_formats(tmp_path, extension, data, title):
    path = tmp_path / f"arquivo.{extension}"
    path.write_bytes(data)
    content = knowledge.read_file(path, extension)
    assert content.title == title and content.parts


READERS = {
    "docx": (knowledge.read_docx, "O arquivo Word está corrompido ou não é um .docx.", {"word/document.xml": "<w:"}),
    "epub": (knowledge.read_epub, "O arquivo EPUB está corrompido ou não é um .epub.",
             {"META-INF/container.xml": "<container"}),
    "pptx": (knowledge.read_pptx, "O arquivo PowerPoint está corrompido ou não é um .pptx.",
             {"ppt/presentation.xml": "<p/>", "ppt/slides/slide1.xml": "<p:sld><a:p>"}),
    "xlsx": (knowledge.read_xlsx, "O arquivo Excel está corrompido ou não é um .xlsx.", {"xl/workbook.xml": "<<"}),
    "odt": (knowledge.read_odt, "O arquivo OpenDocument está corrompido ou não é um .odt.",
            {"content.xml": "<office:document-content>"}),
}


@pytest.mark.parametrize("extension", list(READERS))
def test_corrupt_files_raise_read_error(extension):
    reader, message, broken_xml = READERS[extension]
    members = {name: "<p/>" for name in broken_xml}
    members[list(broken_xml)[-1]] = "<raiz>MARCADOR</raiz>"
    bad_crc = build_zip(members, zipfile.ZIP_STORED).replace(b"MARCADOR", b"MARCADXR", 1)
    samples = [b"PK...", b"PK\x03\x04" + b"\x00" * 40, build_zip({"outro.xml": "<outro/>"}), build_zip(broken_xml),
               bad_crc]
    for data in samples:
        with pytest.raises(ReadError) as error:
            reader(data)
        assert str(error.value) == message


@pytest.mark.parametrize("extension", list(READERS))
def test_members_too_large_after_decompression_are_refused(monkeypatch, extension):
    reader, _, broken_xml = READERS[extension]
    monkeypatch.setattr(knowledge, "MAX_UNZIPPED_BYTES", 1024)
    members = {name: "<p/>" for name in broken_xml}
    members[list(broken_xml)[-1]] = "<raiz>" + " " * 4096 + "</raiz>"
    with pytest.raises(ReadError) as error:
        reader(build_zip(members))
    assert str(error.value) == "O arquivo é grande demais depois de descompactado."


def test_real_limit_refuses_member_over_fifty_megabytes():
    assert knowledge.MAX_UNZIPPED_BYTES == 50 * 1024 * 1024
    data = build_zip({"word/document.xml": b" " * (knowledge.MAX_UNZIPPED_BYTES + 1)})
    assert len(data) < 1024 * 1024
    with pytest.raises(ReadError, match="grande demais depois de descompactado"):
        knowledge.read_docx(data)


def test_upload_new_formats_become_ready_and_searchable(client):
    from nexo import jobs
    headers = login(client)
    files = [
        ("files", ("farol.epub", epub_bytes(), MEDIA["epub"])),
        ("files", ("vendas.xlsx", xlsx_bytes(), MEDIA["xlsx"])),
        ("files", ("treinamento.pptx", pptx_bytes(), MEDIA["pptx"])),
        ("files", ("regulamento.odt", odt_bytes(), MEDIA["odt"])),
    ]
    r = client.post("/api/documents", headers=headers, files=files)
    assert r.status_code == 201, r.text
    created = {d["filename"]: d for d in r.json()}
    assert created["farol.epub"]["title"] == "O Farol de Itaipu"
    assert created["treinamento.pptx"]["title"] == "Treinamento Comercial"
    assert created["regulamento.odt"]["title"] == "Regulamento da Biblioteca"
    assert created["vendas.xlsx"]["title"] == "vendas"
    jobs.wait_idle()
    items = {d["filename"]: d for d in client.get("/api/documents", headers=headers).json()}
    assert all(i["status"] == "READY" for i in items.values()), [(i["filename"], i["error"]) for i in items.values()]
    assert items["farol.epub"]["pages"] == 3 and items["vendas.xlsx"]["pages"] == 2
    assert items["treinamento.pptx"]["pages"] == 3

    r = client.post("/api/search", headers=headers, json={"query": EPUB_QUERY, "rerank": False})
    assert r.status_code == 200, r.text
    first = r.json()["results"][0]
    assert first["document_id"] == created["farol.epub"]["id"] and first["page"] == 3
    assert "querosene" in first["excerpt"]

    for name, extension in (("farol.epub", "epub"), ("vendas.xlsx", "xlsx"), ("treinamento.pptx", "pptx"),
                            ("regulamento.odt", "odt")):
        r = client.get(f"/api/documents/{created[name]['id']}/file", headers=headers)
        assert r.status_code == 200 and r.headers["content-type"] == MEDIA[extension]
        assert r.headers["content-disposition"].startswith("attachment")


def test_corrupt_xlsx_upload_ends_as_failed(client):
    from nexo import jobs
    headers = login(client)
    r = client.post("/api/documents", headers=headers,
                    files=[("files", ("planilha.xlsx", b"PK...", "application/octet-stream"))])
    assert r.status_code == 201, r.text
    jobs.wait_idle()
    doc = client.get(f"/api/documents/{r.json()[0]['id']}", headers=headers).json()
    assert doc["status"] == "FAILED"
    assert doc["error"] == "O arquivo Excel está corrompido ou não é um .xlsx."
    r = client.post("/api/documents", headers=headers,
                    files=[("files", ("texto.odt", b"nao sou zip", "application/octet-stream"))])
    assert r.status_code == 415 and r.json()["code"] == "INVALID_FILE"
