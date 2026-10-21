@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.11 ou mais recente nao encontrado. Instale em https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv (
  echo Criando ambiente virtual...
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
if not exist .venv\.instalado (
  echo Instalando dependencias do Python...
  python -m pip install --upgrade pip
  pip install -r requirements.txt || (pause & exit /b 1)
  echo ok> .venv\.instalado
)
if not exist .env copy .env.example .env >nul
if not exist frontend\dist\index.html (
  where npm >nul 2>nul && (
    echo Compilando a interface...
    pushd frontend
    call npm install
    call npm run build
    popd
  ) || echo Node.js nao encontrado. A API sobe, mas a interface precisa do build em frontend\dist.
)
python -m nexo
pause
