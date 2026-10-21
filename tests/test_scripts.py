import subprocess
import sys
from pathlib import Path

from tests.conftest import login, upload

ROOT = Path(__file__).resolve().parents[1]


def test_reset_password(client):
    from nexo.api.deps import get_users
    get_users().reset_password("admin", "Redefinida2026")
    login(client, "admin", "Redefinida2026")


def test_evaluation_script(client, tmp_path):
    headers = login(client)
    upload(client, headers)
    import os
    env = {**os.environ}
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "avaliar.py"),
                          str(ROOT / "exemplos" / "perguntas-exemplo.jsonl"), "--detalhes"],
                         capture_output=True, text=True, env=env, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert "Somente vetorial" in out.stdout


def test_sample_pdf_generator(tmp_path):
    target = tmp_path / "exemplo.pdf"
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "gerar_pdf_exemplo.py"), str(target)],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert target.read_bytes().startswith(b"%PDF")
