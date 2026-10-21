from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexo.config import get_settings
from nexo.users import UserError, UserStore


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python scripts/redefinir_senha.py <usuario>")
    store = UserStore(get_settings().users_file)
    password = getpass.getpass("Nova senha: ")
    if password != getpass.getpass("Repita a nova senha: "):
        raise SystemExit("As senhas não conferem.")
    try:
        store.reset_password(sys.argv[1], password)
    except UserError as e:
        raise SystemExit(e.message)
    print("Senha redefinida.")


if __name__ == "__main__":
    main()
