from __future__ import annotations

import csv
import html
import io
import json
import posixpath
import re
import zipfile
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

TEXT_EXTENSIONS = ("txt", "md", "csv", "json", "html", "htm")
ZIP_EXTENSIONS = ("docx", "epub", "pptx", "xlsx", "odt")
FILE_EXTENSIONS = ("pdf",) + ZIP_EXTENSIONS + TEXT_EXTENSIONS
PART_CHARS = 2500
CSV_ROWS = 40
MAX_UNZIPPED_BYTES = 50 * 1024 * 1024
MAX_TOTAL_UNZIPPED_BYTES = 200 * 1024 * 1024
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
ODF_TEXT_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
ODF_OFFICE_NS = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"
ODT_PARAGRAPHS = (f"{ODF_TEXT_NS}p", f"{ODF_TEXT_NS}h")
ODT_SKIP = (f"{ODF_TEXT_NS}tracked-changes", f"{ODF_OFFICE_NS}annotation")
ZIP_ERRORS = (zipfile.BadZipFile, EOFError, OSError, ValueError, NotImplementedError, RuntimeError, zlib.error)


class ReadError(RuntimeError):
    pass


@dataclass
class TextContent:
    title: str | None
    parts: list[tuple[int, str]]


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def kind_of(extension: str) -> str:
    return "pdf" if extension == "pdf" else "file"


def decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def split_parts(text: str, size: int = PART_CHARS) -> list[tuple[int, str]]:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > size:
            cut = paragraph.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if current:
                parts.append(current)
                current = ""
            parts.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if current and len(current) + len(paragraph) + 2 > size:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        parts.append(current)
    return [(i, p) for i, p in enumerate(parts, start=1) if len(p) >= 2]


def group_lines(lines: list[str], size: int = PART_CHARS) -> list[tuple[int, str]]:
    parts: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        line = line.strip()[:size]
        if not line:
            continue
        if current and length + len(line) + 1 > size:
            parts.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        parts.append("\n".join(current))
    return [(i, p) for i, p in enumerate(parts, start=1)]


class _HtmlText(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.title: str | None = None
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCKS:
            self.out.append("\n\n" if tag not in ("br", "li", "tr") else "\n")
        if tag == "li":
            self.out.append("- ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title = (self.title or "") + data.strip()
            return
        self.out.append(data)


def _html_text(data: bytes) -> tuple[str | None, str]:
    parser = _HtmlText()
    parser.feed(decode(data))
    text = html.unescape("".join(parser.out))
    text = "\n".join(line.strip() for line in text.split("\n"))
    title = parser.title.strip()[:200] if parser.title and parser.title.strip() else None
    return title, text


def read_html(data: bytes) -> TextContent:
    title, text = _html_text(data)
    return TextContent(title, split_parts(text))


class _Package:
    def __init__(self, data: bytes, message: str):
        self.message = message
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(data))
        except ZIP_ERRORS as e:
            raise ReadError(message) from e
        self.names = set(self.zip.namelist())
        self.budget = MAX_TOTAL_UNZIPPED_BYTES

    def __enter__(self) -> _Package:
        return self

    def __exit__(self, *exc) -> None:
        self.zip.close()

    def read(self, name: str) -> bytes:
        try:
            info = self.zip.getinfo(name)
        except KeyError as e:
            raise ReadError(self.message) from e
        if info.file_size > MAX_UNZIPPED_BYTES or info.file_size > self.budget:
            raise ReadError("O arquivo é grande demais depois de descompactado.")
        self.budget -= info.file_size
        try:
            return self.zip.read(info)
        except ZIP_ERRORS as e:
            raise ReadError(self.message) from e

    def optional(self, name: str) -> bytes | None:
        return self.read(name) if name in self.names else None

    def parse(self, data: bytes) -> ElementTree.Element:
        try:
            return ElementTree.fromstring(data)
        except ElementTree.ParseError as e:
            raise ReadError(self.message) from e

    def xml(self, name: str) -> ElementTree.Element:
        return self.parse(self.read(name))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _dc_title(root: ElementTree.Element) -> str | None:
    for node in root.iter(f"{DC_NS}title"):
        text = " ".join("".join(node.itertext()).split())
        if text:
            return text[:200]
    return None


def _meta_title(package: _Package, name: str) -> str | None:
    data = package.optional(name)
    if not data:
        return None
    try:
        return _dc_title(ElementTree.fromstring(data))
    except ElementTree.ParseError:
        return None


def read_docx(data: bytes) -> TextContent:
    with _Package(data, "O arquivo Word está corrompido ou não é um .docx.") as package:
        root = package.xml("word/document.xml")
        title = _meta_title(package, "docProps/core.xml")
    paragraphs: list[str] = []
    for p in root.iter(f"{WORD_NS}p"):
        pieces = []
        for node in p.iter():
            if node.tag == f"{WORD_NS}t" and node.text:
                pieces.append(node.text)
            elif node.tag == f"{WORD_NS}tab":
                pieces.append("\t")
            elif node.tag in (f"{WORD_NS}br", f"{WORD_NS}cr"):
                pieces.append("\n")
        line = "".join(pieces).strip()
        if line:
            paragraphs.append(line)
    return TextContent(title, split_parts("\n\n".join(paragraphs)))


def read_epub(data: bytes) -> TextContent:
    with _Package(data, "O arquivo EPUB está corrompido ou não é um .epub.") as package:
        container = package.xml("META-INF/container.xml")
        rootfile = next((node.get("full-path") for node in container.iter()
                         if _local(node.tag) == "rootfile" and node.get("full-path") in package.names), None)
        if not rootfile:
            raise ReadError(package.message)
        opf = package.xml(rootfile)
        base = posixpath.dirname(rootfile)
        manifest = {node.get("id"): node for node in opf.iter() if _local(node.tag) == "item" and node.get("id")}
        parts: list[tuple[int, str]] = []
        for ref in opf.iter():
            if _local(ref.tag) != "itemref" or ref.get("idref") not in manifest:
                continue
            item = manifest[ref.get("idref")]
            href = unquote((item.get("href") or "").split("#", 1)[0])
            path = posixpath.normpath(posixpath.join(base, href)).lstrip("/")
            media = item.get("media-type") or ""
            if "html" not in media and not path.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            if not href or path not in package.names:
                continue
            for _, part in split_parts(_html_text(package.read(path))[1]):
                parts.append((len(parts) + 1, part))
    return TextContent(_dc_title(opf), parts)


def _slide_text(root: ElementTree.Element) -> str:
    lines: list[str] = []
    for p in root.iter(f"{DRAWING_NS}p"):
        pieces = []
        for node in p.iter():
            if node.tag == f"{DRAWING_NS}t" and node.text:
                pieces.append(node.text)
            elif node.tag == f"{DRAWING_NS}br":
                pieces.append("\n")
        line = re.sub(r"[ \t]+", " ", "".join(pieces)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def read_pptx(data: bytes) -> TextContent:
    with _Package(data, "O arquivo PowerPoint está corrompido ou não é um .pptx.") as package:
        if "ppt/presentation.xml" not in package.names:
            raise ReadError(package.message)
        slides = sorted((int(match.group(1)), name) for name in package.names
                        if (match := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)))
        parts: list[tuple[int, str]] = []
        for number, name in slides:
            text = _slide_text(package.xml(name))
            if text:
                parts.append((number, text))
        title = _meta_title(package, "docProps/core.xml")
    return TextContent(title, parts)


def _rich_text(node: ElementTree.Element) -> str:
    pieces: list[str] = []
    for child in node:
        tag = _local(child.tag)
        if tag == "t":
            pieces.append(child.text or "")
        elif tag == "r":
            pieces.extend(t.text or "" for t in child if _local(t.tag) == "t")
    return "".join(pieces)


def _column_index(ref: str) -> int | None:
    match = re.match(r"[A-Za-z]+", ref)
    if not match:
        return None
    index = 0
    for letter in match.group(0).upper():
        index = index * 26 + ord(letter) - 64
    return index - 1


def _number(raw: str) -> str:
    try:
        value = float(raw)
    except ValueError:
        return raw.strip()
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.15g}"


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t") or "n"
    if kind == "inlineStr":
        node = next((c for c in cell if _local(c.tag) == "is"), None)
        return _rich_text(node) if node is not None else ""
    raw = next((c.text or "" for c in cell if _local(c.tag) == "v"), "")
    if not raw.strip():
        return ""
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    if kind == "b":
        return "VERDADEIRO" if raw.strip().lower() in ("1", "true") else "FALSO"
    if kind == "n":
        return _number(raw)
    return raw


def _sheet_rows(root: ElementTree.Element, shared: list[str]) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    number = 0
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        ref = row.get("r") or ""
        number = int(ref) if ref.isdigit() else number + 1
        cells: dict[int, str] = {}
        column = -1
        for cell in row:
            if _local(cell.tag) != "c":
                continue
            found = _column_index(cell.get("r") or "")
            column = found if found is not None else column + 1
            value = _cell_value(cell, shared).strip()
            if value:
                cells[column] = value
        if cells:
            values = [""] * (max(cells) + 1)
            for index, value in cells.items():
                values[index] = value
            rows.append((number, values))
    return rows


def _relationships(package: _Package, name: str, base: str) -> list[tuple[str, str, str]]:
    data = package.optional(name)
    if not data:
        return []
    found: list[tuple[str, str, str]] = []
    for node in package.parse(data).iter():
        target = node.get("Target") or ""
        if _local(node.tag) != "Relationship" or not target or node.get("TargetMode") == "External":
            continue
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base, target))
        found.append((node.get("Id") or "", node.get("Type") or "", path))
    return found


def _table_lines(rows: list[tuple[int, list[str]]], sheet: str | None = None) -> list[str]:
    if not rows:
        return []
    header = [h.strip() or f"coluna {i}" for i, h in enumerate(rows[0][1], start=1)]
    lead = f"Planilha {sheet}, linha" if sheet else "Linha"
    lines = []
    for number, row in rows[1:]:
        pairs = [f"{header[i] if i < len(header) else f'coluna {i + 1}'}: {v.strip()}" for i, v in enumerate(row)
                 if v.strip()]
        if pairs:
            lines.append(f"{lead} {number}. " + "; ".join(pairs) + ".")
    if not lines:
        lines = [(f"Planilha {sheet}. " if sheet else "") + "Colunas: " + ", ".join(header) + "."]
    return lines


def _line_parts(lines: list[str]) -> list[tuple[int, str]]:
    starts = range(0, len(lines), CSV_ROWS)
    return [(i, "\n".join(lines[start:start + CSV_ROWS])) for i, start in enumerate(starts, start=1)]


def read_xlsx(data: bytes) -> TextContent:
    with _Package(data, "O arquivo Excel está corrompido ou não é um .xlsx.") as package:
        workbook = package.xml("xl/workbook.xml")
        relationships = _relationships(package, "xl/_rels/workbook.xml.rels", "xl")
        targets = {rid: path for rid, _, path in relationships}
        shared_path = next((path for _, kind, path in relationships if kind.endswith("/sharedStrings")),
                           "xl/sharedStrings.xml")
        shared: list[str] = []
        if shared_path in package.names:
            shared = [_rich_text(si) for si in package.xml(shared_path) if _local(si.tag) == "si"]
        lines: list[str] = []
        sheets = [node for node in workbook.iter() if _local(node.tag) == "sheet"]
        for position, sheet in enumerate(sheets, start=1):
            rid = next((v for k, v in sheet.attrib.items() if k.startswith("{") and _local(k) == "id"), None)
            candidates = (targets.get(rid or ""), f"xl/worksheets/sheet{position}.xml")
            path = next((c for c in candidates if c and c in package.names), None)
            if path is None:
                continue
            name = " ".join((sheet.get("name") or "").split()) or str(position)
            lines.extend(_table_lines(_sheet_rows(package.xml(path), shared), name))
    return TextContent(None, _line_parts(lines))


def _odt_space(text: str | None) -> str:
    return re.sub(r"[ \t\r\n]+", " ", text) if text else ""


def _odt_walk(node: ElementTree.Element, pieces: list[str] | None, paragraphs: list[str]) -> None:
    for child in node:
        tag = child.tag
        if tag in ODT_SKIP:
            pass
        elif tag in ODT_PARAGRAPHS:
            own = [_odt_space(child.text)]
            index = len(paragraphs)
            paragraphs.append("")
            _odt_walk(child, own, paragraphs)
            paragraphs[index] = "".join(own)
        elif pieces is None:
            _odt_walk(child, None, paragraphs)
        elif tag == f"{ODF_TEXT_NS}s":
            pieces.append(" ")
        elif tag == f"{ODF_TEXT_NS}tab":
            pieces.append("\t")
        elif tag == f"{ODF_TEXT_NS}line-break":
            pieces.append("\n")
        else:
            pieces.append(_odt_space(child.text))
            _odt_walk(child, pieces, paragraphs)
        if pieces is not None and child.tail:
            pieces.append(_odt_space(child.tail))


def read_odt(data: bytes) -> TextContent:
    with _Package(data, "O arquivo OpenDocument está corrompido ou não é um .odt.") as package:
        root = package.xml("content.xml")
        title = _meta_title(package, "meta.xml")
    paragraphs: list[str] = []
    _odt_walk(root, None, paragraphs)
    lines = ["\n".join(line.strip() for line in p.split("\n")) for p in paragraphs]
    return TextContent(title, split_parts("\n\n".join(line for line in lines if line.strip())))


def read_csv(data: bytes) -> TextContent:
    text = decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    return TextContent(None, _line_parts(_table_lines(list(enumerate(rows, start=1)))))


def _flatten(value, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(value, list):
        for i, v in enumerate(value, start=1):
            _flatten(v, f"{path}[{i}]", out)
    elif value is not None and str(value).strip():
        out.append(f"{path or 'valor'}: {value}")


def read_json(data: bytes) -> TextContent:
    try:
        value = json.loads(decode(data))
    except json.JSONDecodeError as e:
        raise ReadError(f"O JSON é inválido (linha {e.lineno}).") from e
    lines: list[str] = []
    _flatten(value, "", lines)
    return TextContent(None, group_lines(lines))


def read_text(data: bytes, extension: str) -> TextContent:
    text = decode(data)
    title = None
    if extension == "md":
        match = re.search(r"^#\s+(.+)$", text, re.M)
        if match:
            title = match.group(1).strip()[:200]
    return TextContent(title, split_parts(text))


def read_file(path: Path, extension: str) -> TextContent:
    data = path.read_bytes()
    if extension == "docx":
        return read_docx(data)
    if extension == "epub":
        return read_epub(data)
    if extension == "pptx":
        return read_pptx(data)
    if extension == "xlsx":
        return read_xlsx(data)
    if extension == "odt":
        return read_odt(data)
    if extension in ("html", "htm"):
        return read_html(data)
    if extension == "csv":
        return read_csv(data)
    if extension == "json":
        return read_json(data)
    if extension in ("txt", "md"):
        return read_text(data, extension)
    raise ReadError(f"Formato .{extension} não suportado.")


def looks_valid(data: bytes, extension: str) -> bool:
    if extension == "pdf":
        return data.startswith(b"%PDF")
    if extension in ZIP_EXTENSIONS:
        return data.startswith(b"PK")
    return b"\x00" not in data[:4096]
