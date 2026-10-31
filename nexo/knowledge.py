from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

TEXT_EXTENSIONS = ("txt", "md", "csv", "json", "html", "htm")
FILE_EXTENSIONS = ("pdf", "docx") + TEXT_EXTENSIONS
PART_CHARS = 2500
CSV_ROWS = 40
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


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


def read_html(data: bytes) -> TextContent:
    parser = _HtmlText()
    parser.feed(decode(data))
    text = html.unescape("".join(parser.out))
    text = "\n".join(line.strip() for line in text.split("\n"))
    title = parser.title.strip()[:200] if parser.title and parser.title.strip() else None
    return TextContent(title, split_parts(text))


def read_docx(data: bytes) -> TextContent:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
            core = z.read("docProps/core.xml") if "docProps/core.xml" in z.namelist() else None
    except (zipfile.BadZipFile, KeyError) as e:
        raise ReadError("O arquivo Word está corrompido ou não é um .docx.") from e
    root = ElementTree.fromstring(xml)
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
    title = None
    if core:
        match = re.search(rb"<dc:title>(.*?)</dc:title>", core, re.S)
        if match and match.group(1).strip():
            title = html.unescape(match.group(1).decode("utf-8", errors="ignore")).strip()[:200]
    return TextContent(title, split_parts("\n\n".join(paragraphs)))


def read_csv(data: bytes) -> TextContent:
    text = decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return TextContent(None, [])
    header = [h.strip() or f"coluna {i}" for i, h in enumerate(rows[0], start=1)]
    lines = []
    for number, row in enumerate(rows[1:], start=2):
        pairs = [f"{header[i] if i < len(header) else f'coluna {i + 1}'}: {v.strip()}" for i, v in enumerate(row)
                 if v.strip()]
        if pairs:
            lines.append(f"Linha {number}. " + "; ".join(pairs) + ".")
    if not lines:
        lines = ["Colunas: " + ", ".join(header) + "."]
    parts = []
    for start in range(0, len(lines), CSV_ROWS):
        parts.append("\n".join(lines[start:start + CSV_ROWS]))
    return TextContent(None, [(i, p) for i, p in enumerate(parts, start=1)])


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
    if extension == "docx":
        return data.startswith(b"PK")
    return b"\x00" not in data[:4096]
