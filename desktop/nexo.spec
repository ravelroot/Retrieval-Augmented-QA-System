import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

RAIZ = Path(SPECPATH).parent
VERSAO = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()
FAMILIAS = ("bert", "xlm_roberta", "roberta", "distilbert", "mpnet", "electra", "camembert", "deberta_v2", "modernbert")
METADADOS = ("fastapi", "uvicorn", "pydantic", "pydantic-settings", "sqlalchemy", "chromadb", "qdrant-client", "llama-index-core",
             "sentence-transformers", "transformers", "tokenizers", "huggingface-hub", "safetensors", "torch", "tqdm", "regex",
             "requests", "packaging", "filelock", "numpy", "pyyaml", "pywebview", "opentelemetry-api", "opentelemetry-sdk")

if not (RAIZ / "frontend" / "dist" / "index.html").is_file():
    raise SystemExit("Compile a interface antes: cd frontend && npm ci && npm run build")

datas = [
    (str(RAIZ / "frontend" / "dist"), "frontend/dist"),
    (str(RAIZ / "nexo" / "static"), "nexo/static"),
    (str(RAIZ / "exemplos" / "base-de-teste"), "exemplos/base-de-teste"),
    (str(RAIZ / "VERSION"), "."),
]
datas += collect_data_files("llama_index.core")
datas += collect_data_files("chromadb")
datas += collect_data_files("tiktoken_ext")
for pacote in METADADOS:
    try:
        datas += copy_metadata(pacote)
    except Exception:
        print(f"sem metadados de {pacote}")

hiddenimports = collect_submodules("nexo")
hiddenimports += collect_submodules("chromadb", filter=lambda nome: ".test" not in nome)
hiddenimports += collect_submodules("tiktoken_ext")
hiddenimports += collect_submodules("llama_index.core.postprocessor")
for familia in FAMILIAS:
    hiddenimports += collect_submodules(f"transformers.models.{familia}")
if sys.platform == "win32":
    hiddenimports += ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr"]

binaries = collect_dynamic_libs("chromadb")

versao_windows = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
                                                      VarStruct, VSVersionInfo)
    numeros = tuple(int(x) for x in VERSAO.split(".")) + (0,)
    versao_windows = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numeros, prodvers=numeros),
        kids=[
            StringFileInfo([StringTable("041604B0", [
                StringStruct("CompanyName", "ravelroot"),
                StringStruct("FileDescription", "Nexo"),
                StringStruct("FileVersion", VERSAO),
                StringStruct("InternalName", "Nexo"),
                StringStruct("LegalCopyright", "MIT License"),
                StringStruct("OriginalFilename", "Nexo.exe"),
                StringStruct("ProductName", "Nexo"),
                StringStruct("ProductVersion", VERSAO),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )

a = Analysis(
    [str(RAIZ / "desktop" / "entrada.py")],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "jupyter", "notebook", "pytest", "torchvision", "torchaudio",
              "webview.platforms.gtk", "webview.platforms.qt", "webview.platforms.cocoa", "webview.platforms.cef",
              "webview.platforms.android", "PyQt5", "PyQt6", "PySide2", "PySide6", "gi"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Nexo",
    icon=str(RAIZ / "desktop" / "nexo.ico"),
    version=versao_windows,
    console=False,
    disable_windowed_traceback=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Nexo")
