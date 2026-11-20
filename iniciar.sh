#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null && "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11 ou mais recente não encontrado. Instale em https://www.python.org/downloads/"
  exit 1
fi
if [ ! -d .venv ]; then
  echo "Criando ambiente virtual..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate
if ! cmp -s requirements.txt .venv/requisitos.txt; then
  echo "Instalando as dependências do Python. Na primeira vez leva alguns minutos..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  cp requirements.txt .venv/requisitos.txt
fi
[ -f .env ] || cp .env.example .env
VERSAO=$(tr -d '[:space:]' < VERSION)
if [ ! -f frontend/dist/index.html ] || [ "$(tr -d '[:space:]' < frontend/dist/.versao 2>/dev/null)" != "$VERSAO" ]; then
  if command -v npm >/dev/null; then
    echo "Compilando a interface $VERSAO..."
    (cd frontend && npm install --no-audit --no-fund && npm run build) && echo "$VERSAO" > frontend/dist/.versao
  else
    echo "Node.js não encontrado. A API sobe, mas a interface precisa do build em frontend/dist. Instale em https://nodejs.org"
  fi
fi
ABRIR="--abrir"
if [ -n "$SSH_CONNECTION" ] || { [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$(uname)" != "Darwin" ]; }; then
  ABRIR=""
fi
exec python -m nexo servir $ABRIR
