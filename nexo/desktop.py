from __future__ import annotations

import faulthandler
import html
import http.client
import importlib
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from nexo import __version__

TITULO = "Nexo"
APP_ID = "Ravelroot.Nexo"
RESTAURACAO = "restaurar.zip"
WEBVIEW2 = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
ID_DOCUMENTO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TOKEN = re.compile(r"^[A-Za-z0-9._~+/=-]{1,4096}$")
PROIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
PAGINAS = {"/api/docs": "Referência da API"}
MODULOS = ("webview", "torch", "transformers", "sentence_transformers", "chromadb", "qdrant_client",
           "llama_index.core.postprocessor", "llama_index.embeddings.huggingface", "llama_index.embeddings.openai",
           "llama_index.embeddings.ollama", "llama_index.llms.openai", "llama_index.llms.ollama",
           "llama_index.llms.openai_like", "llama_index.vector_stores.chroma", "llama_index.vector_stores.qdrant",
           "llama_index.postprocessor.cohere_rerank")
MODULOS_WINDOWS = ("clr", "webview.platforms.winforms", "webview.platforms.edgechromium")
ARQUITETURAS = ("BertModel", "XLMRobertaModel", "XLMRobertaForSequenceClassification")
SEM_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
LARGURA, ALTURA, MINIMO = 1280, 820, (960, 640)
ZOOM = 0.75
PREFERENCIAS = "janela.json"
TEMAS = ("light", "dark")
FUNDOS = {"light": "#F5F4F4", "dark": "#080808"}
log = logging.getLogger("nexo.desktop")

MARCA = ('<svg viewBox="0 0 100 100" width="72" height="72" aria-hidden="true">'
         '<rect x=".5" y=".5" width="99" height="99" rx="12" fill="#000" stroke="#2b2a2a"/>'
         '<g transform="translate(20.6 20.6) scale(.588)" fill="#fff"><rect x="18" y="16" width="18" height="68"/>'
         '<rect x="64" y="16" width="18" height="68"/><path d="M36 18L64 82" stroke="#fff" stroke-width="3.5" fill="none"/>'
         '</g></svg>')

ESTILO = """
:root{color-scheme:light;--fundo:#f5f4f4;--texto:#000;--suave:#5c5a5a;--trilho:#e3e1e0}
:root[data-tema=dark]{color-scheme:dark;--fundo:#080808;--texto:#f5f4f4;--suave:#a8a5a4;--trilho:#262525}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{display:grid;place-items:center;background:var(--fundo);color:var(--texto);
font-family:"Segoe UI Variable","Segoe UI",system-ui,sans-serif;user-select:none}
main{display:grid;justify-items:center;gap:14px;max-width:520px;padding:32px;text-align:center}
h1{font-size:22px;font-weight:600;margin:6px 0 0}p{margin:0;color:var(--suave);line-height:1.5;user-select:text}
.barra{width:180px;height:3px;border-radius:3px;background:var(--trilho);overflow:hidden;margin-top:10px}
.barra i{display:block;width:40%;height:100%;background:var(--texto);border-radius:3px;animation:a 1.1s ease-in-out infinite}
@keyframes a{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}
.erro h1{color:#c4271b}:root[data-tema=dark] .erro h1{color:#e89a87}
"""


def tela(titulo: str, texto: str, erro: bool = False, tema: str = "light") -> str:
    barra = "" if erro else '<div class="barra"><i></i></div>'
    tema = tema if tema in TEMAS else "light"
    return (f'<!doctype html><html lang="pt-BR" data-tema="{tema}"><head><meta charset="utf-8"><title>{TITULO}</title>'
            f"<style>{ESTILO}</style>"
            f'</head><body><main class="{"erro" if erro else ""}">{MARCA}<h1>{html.escape(titulo)}</h1>'
            f"<p>{html.escape(texto)}</p>{barra}</main></body></html>")


def geometria(area: tuple[int, int, int, int], escala: float, largura: int = LARGURA, altura: int = ALTURA,
              ocupacao: float = 0.94) -> tuple[int, int, int, int]:
    x0, y0, w, h = area
    lw = max(1, min(round(largura * escala), int(w * ocupacao)))
    lh = max(1, min(round(altura * escala), int(h * ocupacao)))
    return x0 + (w - lw) // 2, y0 + (h - lh) // 2, lw, lh


def _user32():
    import ctypes
    return ctypes.WinDLL("user32")


def _area_de_trabalho(user32, hwnd: int = 0) -> tuple[int, int, int, int] | None:
    import ctypes
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MonitorInfo)]
    if hwnd:
        monitor = user32.MonitorFromWindow(ctypes.c_void_p(hwnd), 2)
    else:
        ponto = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(ponto))
        monitor = user32.MonitorFromPoint(ponto, 2)
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    r = info.rcWork
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def geometria_inicial(largura: int = LARGURA, altura: int = ALTURA) -> dict:
    padrao = {"width": largura, "height": altura, "min_size": (min(MINIMO[0], largura), min(MINIMO[1], altura))}
    if os.name != "nt":
        return padrao
    try:
        user32 = _user32()
        user32.SetProcessDPIAware()
        escala = (user32.GetDpiForSystem() or 96) / 96
        area = _area_de_trabalho(user32)
    except (AttributeError, OSError):
        return padrao
    if not area:
        return padrao
    x, y, w, h = geometria(area, escala, largura, altura)
    lw, lh = round(w / escala), round(h / escala)
    return {"x": round(x / escala), "y": round(y / escala), "width": lw, "height": lh,
            "min_size": (min(MINIMO[0], lw), min(MINIMO[1], lh))}


def _hwnd(janela) -> int:
    try:
        return int(janela.native.Handle.ToInt64())
    except AttributeError:
        return 0


def _barra_de_titulo(janela, tema: str) -> None:
    hwnd = _hwnd(janela)
    if os.name != "nt" or not hwnd:
        return
    import ctypes
    valor = ctypes.c_int(1 if tema == "dark" else 0)
    dwm = ctypes.WinDLL("dwmapi")
    for atributo in (20, 19):
        if dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), atributo, ctypes.byref(valor), ctypes.sizeof(valor)) == 0:
            break
    _user32().SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)


def _centralizar(janela, largura: int, altura: int) -> None:
    hwnd = _hwnd(janela)
    if os.name != "nt" or not hwnd:
        return
    import ctypes
    user32 = _user32()
    area = _area_de_trabalho(user32, hwnd)
    if not area:
        return
    try:
        dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd)) or 96
    except AttributeError:
        dpi = 96
    x, y, w, h = geometria(area, dpi / 96, largura, altura)
    user32.SetWindowPos(ctypes.c_void_p(hwnd), None, x, y, w, h, 0x0004 | 0x0010)


def _zoom(janela) -> None:
    try:
        janela.native.webview.ZoomFactor = ZOOM
    except AttributeError:
        return


def _no_ui(janela, acao) -> None:
    from System import Func, Type
    janela.native.Invoke(Func[Type](acao))


def _preparar_janela(janela, tema: str, largura: int, altura: int, zoom: bool) -> None:
    try:
        _centralizar(janela, largura, altura)
        _barra_de_titulo(janela, tema)
        if zoom:
            _zoom(janela)
    except Exception:
        log.warning("Não foi possível ajustar a janela.", exc_info=True)


def tema_do_windows() -> str:
    if os.name != "nt":
        return "light"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as chave:
            valor, _ = winreg.QueryValueEx(chave, "AppsUseLightTheme")
    except OSError:
        return "light"
    return "dark" if valor == 0 else "light"


def preferencias(raiz: Path) -> dict:
    try:
        dados = json.loads((raiz / PREFERENCIAS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def gravar_preferencias(raiz: Path, dados: dict) -> None:
    destino = raiz / PREFERENCIAS
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, destino)


def empacotado() -> bool:
    return bool(getattr(sys, "frozen", False))


def pasta_raiz() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / TITULO
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / TITULO
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "nexo"


def preparar(raiz: Path) -> None:
    raiz.mkdir(parents=True, exist_ok=True)
    if empacotado():
        os.environ.setdefault("NEXO_DATA_DIR", str(raiz / "data"))
        os.environ.setdefault("HF_HOME", str(raiz / "modelos"))
        os.chdir(raiz)
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def registrar_saida(raiz: Path) -> Path | None:
    if sys.stdout is not None and sys.stderr is not None:
        return None
    pasta = raiz / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "nexo.log"
    try:
        if arquivo.exists() and arquivo.stat().st_size > 5 * 1024 * 1024:
            arquivo.replace(pasta / "nexo.anterior.log")
    except OSError:
        pass
    fluxo = open(arquivo, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = fluxo
    faulthandler.enable(fluxo)
    return arquivo


def porta_livre(host: str, porta: int) -> bool:
    familia = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(familia, socket.SOCK_STREAM) as sock:
        if os.name != "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, porta))
        except OSError:
            return False
    return True


def escolher_porta(host: str, preferida: int) -> int:
    for porta in range(preferida, preferida + 20):
        if 0 < porta < 65536 and porta_livre(host, porta):
            return porta
    familia = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(familia, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def url_local(host: str, porta: int) -> str:
    alvo = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    return f"http://{f'[{alvo}]' if ':' in alvo else alvo}:{porta}"


def travar(raiz: Path) -> int | None:
    fd = os.open(raiz / "nexo.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    (raiz / "instancia.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    return fd


def travar_esperando(raiz: Path, segundos: float) -> int | None:
    limite = time.monotonic() + segundos
    while (fd := travar(raiz)) is None and time.monotonic() < limite:
        time.sleep(0.3)
    return fd


def mensagem(texto: str) -> None:
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, TITULO, 0x40)
    else:
        print(texto)


def _focar(pid: int) -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    achadas: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visitar(hwnd, _):
        dono = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dono))
        if dono.value == pid and user32.IsWindowVisible(hwnd):
            achadas.append(hwnd)
            return False
        return True

    user32.EnumWindows(visitar, 0)
    if not achadas:
        return False
    user32.ShowWindow(achadas[0], 9)
    return bool(user32.SetForegroundWindow(achadas[0]))


def avisar_ja_aberto(raiz: Path) -> None:
    try:
        pid = int(json.loads((raiz / "instancia.json").read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        pid = 0
    if not (pid and _focar(pid)):
        mensagem("O Nexo já está aberto.")


def definir_app_id() -> None:
    if os.name != "nt":
        return
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        log.debug("AppUserModelID não definido.")


def nome_seguro(nome: str | None) -> str:
    from nexo.knowledge import FILE_EXTENSIONS
    limpo = PROIBIDOS.sub("_", (nome or "").replace("\\", "/").rsplit("/", 1)[-1]).strip(" .")
    base, _, extensao = limpo.rpartition(".")
    extensao = extensao.lower()
    base = base[:120].rstrip(" .")
    if not base or extensao not in FILE_EXTENSIONS:
        raise ValueError("Formato de arquivo não suportado.")
    if base.upper() in RESERVADOS:
        base = f"_{base}"
    return f"{base}.{extensao}"


def abrir_no_sistema(arquivo: Path) -> None:
    if os.name == "nt":
        try:
            os.startfile(str(arquivo), "edit" if arquivo.suffix in (".html", ".htm") else "open")
        except OSError:
            subprocess.Popen(["explorer", f"/select,{arquivo}"])
        return
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(arquivo)])


def _falha(status: int, texto: str, codigo: str = "ERROR") -> dict:
    return {"ok": False, "status": status, "code": codigo, "message": texto}


def _falha_http(erro: urllib.error.HTTPError, padrao: str) -> dict:
    try:
        dados = json.loads(erro.read(65536) or b"{}")
    except ValueError:
        dados = {}
    dados = dados if isinstance(dados, dict) else {}
    return _falha(erro.code, str(dados.get("message") or padrao), str(dados.get("code") or "ERROR"))


class Servidor:
    def __init__(self, settings):
        import uvicorn
        from nexo.api.app import create_app
        self.chave = secrets.token_urlsafe(32)
        porta = escolher_porta(settings.host, settings.port)
        self.url = url_local(settings.host, porta)
        config = uvicorn.Config(create_app(janela_chave=self.chave), host=settings.host, port=porta, log_config=None,
                                access_log=False)
        self._uvicorn = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._uvicorn.run, name="nexo-servidor", daemon=True)
        self._thread.start()

    @property
    def entrada(self) -> str:
        return f"/janela?chave={self.chave}"

    def aguardar(self, limite: float = 120.0) -> bool:
        fim = time.monotonic() + limite
        while time.monotonic() < fim and self._thread.is_alive():
            if self._uvicorn.started:
                return True
            time.sleep(0.1)
        return False

    def parar(self, espera: float = 10.0) -> None:
        self._uvicorn.should_exit = True
        self._thread.join(espera)


class Ponte:
    def __init__(self, raiz: Path, tema: str = "light"):
        self._raiz = raiz
        self._temp = raiz / "temp"
        self._base: str | None = None
        self._janela = None
        self._reabrir = False
        self._tema = tema if tema in TEMAS else "light"

    def _ligar(self, base: str, janela) -> None:
        self._base = base
        self._janela = janela

    def _abrir(self, caminho: str, token: str):
        pedido = urllib.request.Request(self._base + caminho, headers={"Authorization": f"Bearer {token}"})
        return SEM_PROXY.open(pedido, timeout=60)

    def _baixar(self, caminho: str, token: str) -> Path:
        with self._abrir(caminho, token) as resposta:
            nome = nome_seguro(resposta.headers.get_filename())
            self._temp.mkdir(parents=True, exist_ok=True)
            destino = Path(tempfile.mkdtemp(dir=self._temp)) / nome
            with open(destino, "wb") as saida:
                shutil.copyfileobj(resposta, saida, 1 << 20)
        return destino

    def _janela_nova(self, titulo: str, url: str) -> None:
        import webview
        geometria_janela = geometria_inicial(1120, 820)
        geometria_janela["min_size"] = (min(640, geometria_janela["width"]), min(480, geometria_janela["height"]))
        nova = webview.create_window(f"{titulo} · {TITULO}", url=url, background_color=FUNDOS[self._tema], text_select=True,
                                     zoomable=True, **geometria_janela)
        if nova is not None:
            _barra_de_titulo(nova, self._tema)

    def definir_tema(self, tema: str) -> dict:
        if tema not in TEMAS:
            return _falha(400, "Tema inválido.")
        if tema != self._tema:
            self._tema = tema
            try:
                gravar_preferencias(self._raiz, {**preferencias(self._raiz), "tema": tema})
            except OSError:
                log.warning("Não foi possível guardar o tema.", exc_info=True)
        import webview
        for janela in list(webview.windows):
            try:
                _barra_de_titulo(janela, tema)
            except Exception:
                log.debug("Barra de título não atualizada.", exc_info=True)
        return {"ok": True}

    def abrir_documento(self, documento_id: str, pagina: int | None = None, token: str = "") -> dict:
        if not self._base:
            return _falha(503, "O Nexo ainda está abrindo. Tente de novo em instantes.")
        if not (isinstance(documento_id, str) and ID_DOCUMENTO.fullmatch(documento_id)):
            return _falha(400, "Documento inválido.")
        if not (isinstance(token, str) and TOKEN.fullmatch(token)):
            return _falha(401, "Sua sessão expirou. Entre de novo.", "UNAUTHORIZED")
        try:
            arquivo = self._baixar(f"/api/documents/{documento_id}/file", token)
        except urllib.error.HTTPError as e:
            return _falha_http(e, "Não foi possível abrir o arquivo.")
        except ValueError as e:
            return _falha(415, str(e))
        except OSError:
            log.warning("Falha ao baixar o documento %s", documento_id, exc_info=True)
            return _falha(502, "Não foi possível abrir o arquivo.")
        if arquivo.suffix == ".pdf":
            valida = isinstance(pagina, int) and not isinstance(pagina, bool) and 0 < pagina <= 100000
            self._janela_nova(arquivo.stem, arquivo.as_uri() + (f"#page={pagina}" if valida else ""))
        else:
            abrir_no_sistema(arquivo)
        return {"ok": True}

    def abrir_pagina(self, caminho: str) -> dict:
        titulo = PAGINAS.get(caminho) if isinstance(caminho, str) else None
        if not self._base or titulo is None:
            return _falha(404, "Página não encontrada.")
        self._janela_nova(titulo, self._base + caminho)
        return {"ok": True}

    def restaurar_backup(self, token: str = "") -> dict:
        if not self._base or self._janela is None:
            return _falha(503, "O Nexo ainda está abrindo. Tente de novo em instantes.")
        if not (isinstance(token, str) and TOKEN.fullmatch(token)):
            return _falha(401, "Sua sessão expirou. Entre de novo.", "UNAUTHORIZED")
        try:
            with self._abrir("/api/auth/me", token) as resposta:
                conta = json.loads(resposta.read(65536))
        except urllib.error.HTTPError as e:
            return _falha_http(e, "Não foi possível conferir a sua conta.")
        except (OSError, ValueError):
            return _falha(502, "Não foi possível conferir a sua conta.")
        if not isinstance(conta, dict) or conta.get("role") != "admin":
            return _falha(403, "Só administradores restauram backups.", "FORBIDDEN")
        import webview
        from nexo.maintenance import MaintenanceError, read_manifest
        escolha = self._janela.create_file_dialog(webview.FileDialog.OPEN, file_types=("Backup do Nexo (*.zip)",))
        if not escolha:
            return {"ok": False, "cancelado": True}
        origem = Path(escolha[0])
        try:
            manifesto = read_manifest(origem)
        except MaintenanceError as e:
            return _falha(400, str(e))
        origem_backup = ", ".join(x for x in (f"versão {manifesto['versao']}" if manifesto.get("versao") else "",
                                              str(manifesto.get("criado_em") or "")[:10]) if x)
        texto = (f"Restaurar o backup{f' ({origem_backup})' if origem_backup else ''}? O Nexo vai fechar, guardar os dados "
                 "atuais numa cópia ao lado da pasta de dados e abrir de novo com o backup. Os documentos são reindexados "
                 "sozinhos.")
        if not self._janela.create_confirmation_dialog("Restaurar backup", texto):
            return {"ok": False, "cancelado": True}
        shutil.copyfile(origem, self._raiz / RESTAURACAO)
        self._reabrir = True
        self._janela.destroy()
        return {"ok": True}


def restaurar_pendente(raiz: Path) -> str | None:
    pendente = raiz / RESTAURACAO
    if not pendente.is_file():
        return None
    from nexo.config import Settings
    from nexo.maintenance import MaintenanceError, restore_backup
    try:
        resultado = restore_backup(pendente, Settings().data_dir, replace=True)
    except (MaintenanceError, OSError) as e:
        log.exception("Falha ao restaurar o backup")
        return str(e)
    finally:
        pendente.unlink(missing_ok=True)
    log.info("Backup restaurado: %s arquivo(s), %s documento(s) na fila.", resultado["files"], resultado["queued"])
    return None


def primeira_abertura(settings) -> int:
    if settings.setup_file.exists():
        return 0
    from sqlalchemy import func, select
    from nexo import audit, db, onboarding, sample
    from nexo.users import DEFAULT_ADMIN_USERNAME
    db.engine()
    with db.session() as s:
        if s.scalar(select(func.count()).select_from(db.DocumentRow)):
            onboarding.finish(settings, DEFAULT_ADMIN_USERNAME)
            return 0
        criado = sample.create(s, DEFAULT_ADMIN_USERNAME, enqueue=False)
        base_id, total = criado.base.id, len(criado.added)
    audit.record("base.sample", "base", base_id, {"added": total, "origem": "primeira abertura"}, actor=DEFAULT_ADMIN_USERNAME)
    onboarding.finish(settings, DEFAULT_ADMIN_USERNAME)
    log.info("Primeira abertura: Base de teste criada com %d arquivo(s), usando %s com %s.", total, settings.llm_provider,
             settings.llm_model)
    return total


def _indexando() -> bool:
    from sqlalchemy import func, select
    from nexo import db
    with db.session() as s:
        total = s.scalar(select(func.count()).select_from(db.DocumentRow)
                         .where(db.DocumentRow.status.in_(["PENDING", "PROCESSING"])))
    return bool(total)


def _ao_fechar(janela, ponte: Ponte, estado: dict) -> bool:
    if ponte._reabrir or "servidor" not in estado:
        return True
    try:
        if not _indexando():
            return True
    except Exception:
        log.warning("Não foi possível conferir a fila de indexação.", exc_info=True)
        return True
    return bool(janela.create_confirmation_dialog(
        "Fechar o Nexo?", "Há documentos sendo indexados. Se fechar agora, a indexação continua na próxima vez que o "
        "Nexo abrir."))


def _fechar_outras(principal) -> None:
    import webview
    for janela in list(webview.windows):
        if janela is not principal:
            janela.destroy()


def _ao_carregar(janela, estado: dict) -> None:
    servidor = estado.get("servidor")
    if estado.get("zoom") or servidor is None or not str(janela.get_current_url() or "").startswith(servidor.url):
        return
    estado["zoom"] = True
    try:
        _no_ui(janela, lambda: _zoom(janela))
    except Exception:
        log.warning("Não foi possível ajustar o zoom.", exc_info=True)


def _iniciar(janela, ponte: Ponte, estado: dict, raiz: Path, registro: Path | None) -> None:
    import webview
    from pydantic import ValidationError
    onde = f"Veja os detalhes em {registro}." if registro else "Veja os detalhes no terminal."
    tema = ponte._tema
    if os.name == "nt" and webview.renderer != "edgechromium":
        janela.load_html(tela("Falta o Microsoft Edge WebView2", "O Nexo usa o WebView2 do Windows para mostrar a "
                              f"janela. Instale pelo endereço {WEBVIEW2} e abra o Nexo de novo.", erro=True, tema=tema))
        return
    try:
        falha = restaurar_pendente(raiz)
        if falha:
            janela.load_html(tela("Não foi possível restaurar o backup", f"{falha} Os dados atuais continuam como "
                                  "estavam. Feche e abra o Nexo de novo.", erro=True, tema=tema))
            return
        from nexo import logs
        from nexo.config import get_settings
        settings = get_settings()
        logs.setup(settings)
        primeira_abertura(settings)
        servidor = Servidor(settings)
        estado["servidor"] = servidor
        if not servidor.aguardar():
            janela.load_html(tela("O Nexo não conseguiu abrir", onde, erro=True, tema=tema))
            return
        ponte._ligar(servidor.url, janela)
        log.info("Nexo %s aberto em %s", __version__, servidor.url)
        janela.load_url(servidor.url + servidor.entrada)
    except ValidationError as e:
        campos = "; ".join(f"NEXO_{'.'.join(str(x) for x in err.get('loc', [])).upper()}: {err.get('msg')}"
                           for err in e.errors())
        janela.load_html(tela("O arquivo .env tem valores inválidos", f"{campos}. Corrija e abra o Nexo de novo.", erro=True,
                              tema=tema))
    except Exception:
        log.exception("Falha ao abrir o Nexo")
        janela.load_html(tela("O Nexo não conseguiu abrir", onde, erro=True, tema=tema))


def _reabrir() -> None:
    comando = [sys.executable] if empacotado() else [sys.executable, "-m", "nexo"]
    opcoes = {"close_fds": True}
    if os.name == "nt":
        opcoes["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opcoes["start_new_session"] = True
    subprocess.Popen([*comando, "--reabrir"], **opcoes)


def _encerrar(raiz: Path, ponte: Ponte, estado: dict) -> None:
    servidor = estado.get("servidor")
    if servidor is not None:
        servidor.parar()
    jobs = sys.modules.get("nexo.jobs")
    if jobs is not None:
        jobs.shutdown()
    shutil.rmtree(raiz / "temp", ignore_errors=True)
    if ponte._reabrir:
        try:
            _reabrir()
        except OSError:
            log.exception("Não foi possível abrir o Nexo de novo")
    logging.shutdown()
    os._exit(0)


def abrir(reabrir: bool = False) -> None:
    raiz = pasta_raiz()
    preparar(raiz)
    if travar_esperando(raiz, 30 if reabrir else 0) is None:
        avisar_ja_aberto(raiz)
        return
    registro = registrar_saida(raiz)
    definir_app_id()
    shutil.rmtree(raiz / "temp", ignore_errors=True)
    try:
        import webview
    except ImportError:
        sys.exit("Falta o pywebview. Instale as dependências com: pip install -r requirements.txt")
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    salvo = preferencias(raiz).get("tema")
    tema = salvo if salvo in TEMAS else tema_do_windows()
    ponte = Ponte(raiz, tema)
    estado: dict = {}
    janela = webview.create_window(TITULO, html=tela("Abrindo o Nexo", "Preparando as bases, os agentes e as conversas.",
                                                     tema=tema),
                                   js_api=ponte, background_color=FUNDOS[tema], text_select=True, zoomable=True,
                                   **geometria_inicial())
    janela.events.before_show += lambda window: _preparar_janela(window, ponte._tema, LARGURA, ALTURA, True)
    janela.events.loaded += lambda window: _ao_carregar(window, estado)
    janela.events.closing += lambda window: _ao_fechar(window, ponte, estado)
    janela.events.closed += lambda: _fechar_outras(janela)
    try:
        webview.start(_iniciar, (janela, ponte, estado, raiz, registro), gui="edgechromium" if os.name == "nt" else None,
                      private_mode=False, storage_path=str(raiz / "janela"),
                      debug=os.environ.get("NEXO_JANELA_DEPURAR") == "1")
    except Exception:
        log.exception("Não foi possível abrir a janela")
        mensagem(f"O Nexo não conseguiu abrir a janela. Confira se o Microsoft Edge WebView2 está instalado ({WEBVIEW2}) "
                 "e abra o Nexo de novo.")
    _encerrar(raiz, ponte, estado)


def _pedir(base: str, metodo: str, caminho: str, corpo: dict | None = None,
           cabecalhos: dict | None = None) -> tuple[int, dict, bytes]:
    alvo = urllib.parse.urlsplit(base)
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    extras = {"Content-Type": "application/json"} if dados is not None else {}
    conexao = http.client.HTTPConnection(alvo.hostname, alvo.port, timeout=180)
    try:
        conexao.request(metodo, caminho, body=dados, headers={**(cabecalhos or {}), **extras})
        resposta = conexao.getresponse()
        return resposta.status, {k.lower(): v for k, v in resposta.getheaders()}, resposta.read()
    finally:
        conexao.close()


def _verificar_servidor(pasta: Path, anotar) -> None:
    from sqlalchemy import func, select
    from nexo import db, jobs, sample
    from nexo.api.app import WINDOW_COOKIE
    from nexo.config import get_settings
    from nexo.users import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
    servidor = Servidor(get_settings())
    try:
        if not anotar(servidor.aguardar(90), "servidor local", servidor.url):
            return
        status, _, _ = _pedir(servidor.url, "GET", "/api/health/ready")
        anotar(status == 200, "saúde do servidor", str(status))
        status, _, _ = _pedir(servidor.url, "GET", "/")
        anotar(status == 403, "painel fechado fora da janela", str(status))
        status, cabecalhos, _ = _pedir(servidor.url, "GET", servidor.entrada)
        cookie = cabecalhos.get("set-cookie", "").split(";", 1)[0]
        anotar(status == 303 and cookie.startswith(f"{WINDOW_COOKIE}="), "entrada da janela", str(status))
        status, _, corpo = _pedir(servidor.url, "GET", "/", cabecalhos={"Cookie": cookie})
        anotar(status == 200 and b'id="root"' in corpo, "painel dentro da janela", str(status))
        status, _, corpo = _pedir(servidor.url, "POST", "/api/auth/login",
                                  {"username": DEFAULT_ADMIN_USERNAME, "password": DEFAULT_ADMIN_PASSWORD})
        token = json.loads(corpo).get("token", "") if status == 200 else ""
        if not anotar(bool(token), "login", str(status)):
            return
        with db.session() as s:
            criado = sample.create(s, DEFAULT_ADMIN_USERNAME, enqueue=False)
            bot_id, ids = criado.bot.id, list(criado.added)
        for documento_id in ids:
            jobs.process(documento_id)
        with db.session() as s:
            prontos = s.scalar(select(func.count()).select_from(db.DocumentRow)
                               .where(db.DocumentRow.id.in_(ids), db.DocumentRow.status == "READY"))
        anotar(bool(ids) and prontos == len(ids), "indexação da base de teste", f"{prontos}/{len(ids)}")
        status, _, corpo = _pedir(servidor.url, "POST", "/api/ask", {"question": sample.SUGGESTIONS[1], "bot_id": bot_id},
                                  {"Authorization": f"Bearer {token}"})
        resposta = json.loads(corpo) if status == 200 else {}
        anotar(bool(resposta.get("answered")), "resposta com fonte", f"{len(resposta.get('sources', []))} fonte(s)")
        ponte = Ponte(pasta)
        ponte._ligar(servidor.url, None)
        arquivo = ponte._baixar(f"/api/documents/{ids[0]}/file", token)
        anotar(arquivo.stat().st_size > 0, "cópia do documento para abrir", arquivo.name)
    finally:
        servidor.parar()


def verificar(saida: str | None = None) -> int:
    console = sys.stdout is not None
    if sys.stdout is None or sys.stderr is None:
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    linhas = [f"Nexo {__version__} · verificação do pacote"]
    falhas = 0

    def anotar(ok: bool, rotulo: str, detalhe: str = "") -> bool:
        nonlocal falhas
        falhas += not ok
        linhas.append(f"[{'ok' if ok else 'falha'}] {rotulo}" + (f": {detalhe}" if detalhe else ""))
        return ok

    for modulo in MODULOS + (MODULOS_WINDOWS if os.name == "nt" else ()):
        try:
            importlib.import_module(modulo)
            anotar(True, f"módulo {modulo}")
        except Exception as e:
            anotar(False, f"módulo {modulo}", repr(e))
    try:
        transformers = importlib.import_module("transformers")
        for nome in ARQUITETURAS:
            getattr(transformers, nome)
        anotar(True, "arquiteturas do transformers", ", ".join(ARQUITETURAS))
    except Exception as e:
        anotar(False, "arquiteturas do transformers", repr(e))
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="nexo-verificar-", ignore_cleanup_errors=True) as temp:
        pasta = Path(temp)
        os.chdir(pasta)
        os.environ.update({"NEXO_DATA_DIR": str(pasta / "data"), "NEXO_EMBED_PROVIDER": "hash",
                           "NEXO_LLM_PROVIDER": "extrativo", "NEXO_RERANKER": "none", "NEXO_HOST": "127.0.0.1",
                           "NEXO_PORT": str(escolher_porta("127.0.0.1", 18765)), "NEXO_REQUIRE_PASSWORD_CHANGE": "false",
                           "NEXO_MIN_SIMILARITY": "0.1",
                           "ANONYMIZED_TELEMETRY": "False"})
        try:
            _verificar_servidor(pasta, anotar)
        except Exception as e:
            log.exception("Falha na verificação")
            anotar(False, "fluxo completo", repr(e))
        finally:
            os.chdir(original)
    linhas.append(f"{len(linhas) - 1 - falhas} ok, {falhas} falha(s).")
    texto = "\n".join(linhas)
    if saida:
        Path(saida).write_text(texto + "\n", encoding="utf-8")
    if console:
        print(texto)
    return 1 if falhas else 0
