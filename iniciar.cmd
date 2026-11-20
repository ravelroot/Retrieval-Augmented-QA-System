@echo off
setlocal
cd /d "%~dp0"
set PY=
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set PY=py -3
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set PY=python
)
if not defined PY (
  echo Python 3.11 ou mais recente nao encontrado. Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  echo Criando ambiente virtual...
  %PY% -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
fc /b requirements.txt .venv\requisitos.txt >nul 2>nul
if errorlevel 1 (
  echo Instalando as dependencias do Python. Na primeira vez leva alguns minutos...
  python -m pip install --upgrade pip
  pip install -r requirements.txt || (echo Falha ao instalar as dependencias. Confira a internet e rode de novo. & pause & exit /b 1)
  copy /y requirements.txt .venv\requisitos.txt >nul
)
if not exist .env copy .env.example .env >nul
for /f "usebackq delims=" %%v in ("VERSION") do set VERSAO=%%v
set CONSTRUIR=
if not exist frontend\dist\index.html set CONSTRUIR=1
findstr /x /c:"%VERSAO%" frontend\dist\.versao >nul 2>nul || set CONSTRUIR=1
if defined CONSTRUIR (
  where npm >nul 2>nul && (
    echo Compilando a interface %VERSAO%...
    pushd frontend
    call npm install --no-audit --no-fund
    call npm run build
    popd
    if exist frontend\dist\index.html (>frontend\dist\.versao echo %VERSAO%)
  ) || echo Node.js nao encontrado. A API sobe, mas a interface precisa do build em frontend\dist. Instale em https://nodejs.org
)
python -m nexo servir --abrir
pause
