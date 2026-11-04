from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from nexo import __version__, knowledge
from nexo.config import Settings

MAX_REDIRECTS = 5
CONTENT_TYPES = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/csv": "csv",
    "application/json": "json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/epub+zip": "epub",
}


class LinkError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Fetched:
    url: str
    data: bytes
    extension: str
    filename: str


def validate(url: str, settings: Settings) -> urllib.parse.ParseResult:
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except ValueError as e:
        raise LinkError("INVALID_URL", "Informe um endereço válido, começando com http:// ou https://.") from e
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LinkError("INVALID_URL", "Informe um endereço válido, começando com http:// ou https://.")
    if parsed.username or parsed.password:
        raise LinkError("INVALID_URL", "Não use usuário e senha dentro do endereço.")
    if not settings.allow_private_urls:
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise LinkError("UNREACHABLE", f"Não encontrei o endereço {parsed.hostname}.") from e
        for info in infos:
            address = ipaddress.ip_address(info[4][0].split("%", 1)[0])
            if (address.is_private or address.is_loopback or address.is_link_local or address.is_multicast
                    or address.is_reserved or address.is_unspecified):
                raise LinkError("PRIVATE_URL", "Endereços da rede interna estão bloqueados. Libere com NEXO_ALLOW_PRIVATE_URLS=true.")
    return parsed


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise LinkError("TOO_MANY_REDIRECTS", "O endereço redireciona vezes demais.")
        validate(newurl, self.settings)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _extension(content_type: str, path: str) -> str | None:
    found = CONTENT_TYPES.get(content_type)
    if found:
        return found
    guess = knowledge.extension_of(path)
    return guess if guess in knowledge.FILE_EXTENSIONS else None


def _filename(parsed: urllib.parse.ParseResult, extension: str, disposition: str) -> str:
    match = re.search(r'filename="?([^";]+)"?', disposition or "")
    if match:
        name = match.group(1).strip()
    else:
        tail = urllib.parse.unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1]) if parsed.path.strip("/") else ""
        name = tail or parsed.hostname or "pagina"
    name = re.sub(r"[^\w.\- ()]+", "_", name, flags=re.UNICODE).strip("._ ") or "pagina"
    if knowledge.extension_of(name) != extension:
        name = f"{name}.{extension}"
    return name[:255]


def fetch(url: str, settings: Settings) -> Fetched:
    parsed = validate(url, settings)
    opener = urllib.request.build_opener(_Redirects(settings))
    request = urllib.request.Request(parsed.geturl(), headers={
        "User-Agent": f"Nexo/{__version__} (importador de links)",
        "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain,text/markdown,text/csv,application/json;q=0.9,*/*;q=0.5",
    })
    limit = settings.max_upload_mb * 1024 * 1024
    try:
        with opener.open(request, timeout=settings.link_timeout) as response:
            final = urllib.parse.urlparse(response.geturl())
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > limit:
                raise LinkError("FILE_TOO_LARGE", f"O conteúdo passa do limite de {settings.max_upload_mb} MB.")
            data = response.read(limit + 1)
            disposition = response.headers.get("Content-Disposition") or ""
    except LinkError:
        raise
    except urllib.error.HTTPError as e:
        raise LinkError("HTTP_ERROR", f"O endereço respondeu HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, LinkError):
            raise e.reason from e
        raise LinkError("UNREACHABLE", f"Não foi possível abrir o endereço: {e.reason}") from e
    except TimeoutError as e:
        raise LinkError("UNREACHABLE", "O endereço demorou demais para responder.") from e
    if len(data) > limit:
        raise LinkError("FILE_TOO_LARGE", f"O conteúdo passa do limite de {settings.max_upload_mb} MB.")
    extension = _extension(content_type, final.path)
    if extension is None:
        raise LinkError("UNSUPPORTED", f"O endereço devolveu um conteúdo que o Nexo não lê ({content_type or 'tipo desconhecido'}).")
    if not data.strip():
        raise LinkError("EMPTY", "O endereço devolveu uma página vazia.")
    if not knowledge.looks_valid(data, extension):
        raise LinkError("INVALID_FILE", f"O conteúdo não parece um .{extension} válido.")
    return Fetched(url=final.geturl(), data=data, extension=extension, filename=_filename(final, extension, disposition))
