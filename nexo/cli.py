from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from nexo import __version__

SYMBOLS = {"ok": "ok  ", "warn": "aviso", "fail": "falha", "info": "info"}


def _settings():
    from nexo.config import get_settings
    try:
        return get_settings()
    except ValidationError as e:
        lines = []
        for err in e.errors():
            name = "NEXO_" + ".".join(str(x) for x in err.get("loc", [])).upper()
            lines.append(f"  {name}: {err.get('msg')} (valor recebido: {err.get('input')!r})")
        sys.exit("O arquivo .env tem valores inválidos:\n" + "\n".join(lines) + "\nCorrija e rode de novo.")


PRESETS = (
    ("ollama", "Ollama no seu computador (gratuito, roda local)", None, "llama3.1"),
    ("openai", "OpenAI (precisa de uma chave de API)", None, "gpt-4o-mini"),
    ("compativel", "Groq (rápido, na nuvem, com plano gratuito)", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    ("compativel", "OpenRouter", "https://openrouter.ai/api/v1", None),
    ("compativel", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", None),
    ("compativel", "LM Studio no seu computador", "http://localhost:1234/v1", None),
    ("compativel", "Outro serviço compatível com a OpenAI", None, None),
    ("extrativo", "Sem modelo, só para testar a instalação", None, None),
)


def _ask(label: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = getpass.getpass(f"  {label}: ") if secret else input(f"  {label}{suffix}: ")
    except EOFError:
        value = ""
    return value.strip() or (default or "")


def configure(_: argparse.Namespace) -> None:
    from nexo import db, runtime
    from nexo.rag import providers
    from nexo.users import DEFAULT_ADMIN_USERNAME, UserError, UserStore
    settings = _settings()
    db.engine()
    users = UserStore(settings.users_file)
    print(f"\nAssistente de configuração do Nexo {__version__}. Enter mantém o valor entre colchetes.\n")
    if users.default_admin_active():
        print("A conta admin ainda usa a senha padrão. Escolha uma nova (8 a 72 caracteres, letras e números).")
        while True:
            new = _ask("Nova senha do admin", secret=True)
            if new == _ask("Repita a nova senha", secret=True):
                try:
                    users.reset_password(DEFAULT_ADMIN_USERNAME, new)
                    print("  Senha trocada.\n")
                    break
                except UserError as e:
                    print(f"  {e.message}")
            else:
                print("  As senhas não conferem.")
    print("Quem escreve as respostas?")
    for i, (_, label, _, _) in enumerate(PRESETS, start=1):
        print(f"  {i}. {label}")
    current = next((i for i, p in enumerate(PRESETS, start=1) if p[0] == settings.llm_provider), 1)
    choice = _ask("Opção", str(current))
    index = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(PRESETS) else current - 1
    provider, label, url, model = PRESETS[index]
    values: dict = {"llm_provider": provider}
    if provider == "ollama":
        values["ollama_url"] = _ask("Endereço do Ollama", settings.ollama_url)
        values["llm_model"] = _ask("Modelo", settings.llm_model if settings.llm_provider == "ollama" else model)
    elif provider in ("openai", "compativel"):
        if provider == "compativel":
            values["openai_base_url"] = _ask("Endereço do serviço", url or settings.openai_base_url)
        keep = " (Enter mantém a atual)" if settings.openai_api_key else ""
        key = _ask(f"Chave da API{keep}", secret=True)
        if key:
            values["openai_api_key"] = key
        values["llm_model"] = _ask("Modelo", model or (settings.llm_model if settings.llm_provider == provider else None))
    try:
        candidate, fields = runtime.trial(settings, values)
    except runtime.AdjustError as e:
        fields = e.fields
    if fields:
        sys.exit("Revise: " + "; ".join(f"{k}: {v}" for k, v in fields.items()))
    if provider != "extrativo":
        print(f"\nTestando {label}…")
        result = providers.probe("llm", candidate)
        print(f"  {'ok' if result['ok'] else 'falhou'}: {result['detail']}")
        if not result["ok"] and _ask("Salvar mesmo assim? (s/n)", "n").lower() != "s":
            sys.exit("Nada foi salvo.")
    changed = runtime.update(settings, values, "linha de comando")
    print(f"\nPronto: {len(changed)} ajuste(s) salvo(s) em {settings.overrides_file}. Já valem na próxima vez que o Nexo abrir.")
    print("Confira tudo com: python -m nexo diagnostico")


def password(args: argparse.Namespace) -> None:
    from nexo.users import UserError, UserStore
    settings = _settings()
    users = UserStore(settings.users_file)
    if users.get(args.usuario) is None:
        sys.exit(f"Conta '{args.usuario}' não encontrada. Veja as contas com: python -m nexo contas")
    new = getpass.getpass(f"Nova senha para {args.usuario}: ")
    if new != getpass.getpass("Repita a nova senha: "):
        sys.exit("As senhas não conferem.")
    try:
        users.reset_password(args.usuario, new)
    except UserError as e:
        sys.exit(e.message)
    users.unlock(args.usuario)
    print("Senha redefinida. As sessões abertas dessa conta foram encerradas.")


def doctor(args: argparse.Namespace) -> None:
    from nexo import db, maintenance
    from nexo.users import UserStore
    settings = _settings()
    db.engine()
    report = maintenance.diagnose(settings, UserStore(settings.users_file), deep=args.completo)
    group = ""
    for check in report["checks"]:
        if check["group"] != group:
            group = check["group"]
            print(f"\n{group}")
        print(f"  [{SYMBOLS[check['status']]}] {check['label']}: {check['detail']}")
        if check.get("hint") and check["status"] in ("warn", "fail"):
            print(f"          {check['hint']}")
    print(f"\n{report['ok']} ok, {report['warn']} aviso(s), {report['fail']} falha(s).")
    if report["fail"]:
        sys.exit(1)


def backup(args: argparse.Namespace) -> None:
    from nexo import audit, db, maintenance
    settings = _settings()
    db.engine()
    target = Path(args.saida or f"nexo-backup-{datetime.now().strftime('%Y-%m-%d-%H%M')}.zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = maintenance.create_backup(settings, target)
    audit.record("system.backup", "system", None, {"bytes": manifest["bytes"], "origem": "linha de comando"}, actor="sistema")
    print(f"Backup gravado em {target} ({manifest['bytes'] / 1024 / 1024:.1f} MB, {manifest['documentos']} documento(s)).")
    if not manifest["inclui_banco"]:
        print("O banco relacional é externo: faça o backup dele com a ferramenta do próprio banco.")


def restore(args: argparse.Namespace) -> None:
    from nexo import maintenance
    settings = _settings()
    try:
        result = maintenance.restore_backup(Path(args.arquivo), settings.data_dir, replace=args.substituir)
    except maintenance.MaintenanceError as e:
        sys.exit(str(e))
    print(f"Backup da versão {result['manifest'].get('versao')} restaurado em {settings.data_dir} ({result['files']} arquivo(s)).")
    if result["previous"]:
        print(f"Os dados anteriores foram guardados em {result['previous']}.")
    print(f"{result['queued']} documento(s) serão reindexados quando o Nexo abrir.")


def reindex(args: argparse.Namespace) -> None:
    from sqlalchemy import select
    from nexo import db, jobs, maintenance
    from nexo.rag import providers
    settings = _settings()
    db.engine()
    with db.session() as s:
        if args.todos:
            ids = list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status.in_(["READY", "FAILED", "PENDING"]))))
        elif args.desatualizados:
            ids = maintenance.outdated_ids(s, providers.index_signature(settings))
        else:
            ids = list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status.in_(["FAILED", "PENDING", "PROCESSING"]))))
    if not ids:
        print("Nada para reindexar.")
        return
    print(f"Reindexando {len(ids)} documento(s). Mantenha o Nexo fechado enquanto isso.")
    failed = 0
    for i, document_id in enumerate(ids, start=1):
        jobs.process(document_id)
        with db.session() as s:
            row = s.get(db.DocumentRow, document_id)
            if row is None:
                continue
            mark = "ok" if row.status == "READY" else "falhou"
            failed += row.status != "READY"
            print(f"  {i}/{len(ids)} {row.title}: {mark}" + (f" ({row.error})" if row.status != "READY" and row.error else ""))
    print(f"Pronto: {len(ids) - failed} ok, {failed} com falha.")


def sample_base(args: argparse.Namespace) -> None:
    from nexo import audit, db, jobs, sample
    _settings()
    db.engine()
    with db.session() as s:
        try:
            result = sample.create(s, args.conta, enqueue=False)
        except sample.SampleError as e:
            sys.exit(str(e))
        base_id, bot_name, added, existed = result.base.id, result.bot.name, list(result.added), result.existed
    audit.record("base.sample", "base", base_id, {"added": len(added), "origem": "linha de comando"}, actor=args.conta)
    if existed and not added:
        print(f"A {sample.BASE_NAME} já existe com todos os arquivos. Converse com o {bot_name} em Chats com agentes.")
        return
    print(f"Indexando {len(added)} arquivo(s) da {sample.BASE_NAME}…")
    for document_id in added:
        jobs.process(document_id)
        with db.session() as s:
            row = s.get(db.DocumentRow, document_id)
            print(f"  {row.title}: {'ok' if row.status == 'READY' else row.error}")
    print(f"Pronto. Converse com o {bot_name} em Chats com agentes.")


def accounts(_: argparse.Namespace) -> None:
    from nexo.users import UserStore
    settings = _settings()
    users = UserStore(settings.users_file).all()
    width = max((len(u.username) for u in users), default=7)
    for u in users:
        role = "administrador" if u.role == "admin" else "usuário"
        print(f"  {u.username.ljust(width)}  {role.ljust(13)}  {u.name}  (último acesso: {u.last_login_at or 'nunca'})")
    print(f"{len(users)} conta(s) em {settings.users_file}.")


def version(_: argparse.Namespace) -> None:
    print(f"Nexo {__version__}")


def window(args: argparse.Namespace) -> None:
    from nexo import desktop
    desktop.abrir(reabrir=getattr(args, "reabrir", False))


def check(args: argparse.Namespace) -> None:
    from nexo import desktop
    sys.exit(desktop.verificar(args.saida))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m nexo", description="Aplicativo do Nexo e ferramentas de manutenção.")
    root.add_argument("--reabrir", action="store_true", help=argparse.SUPPRESS)
    sub = root.add_subparsers(dest="comando", metavar="comando")
    sub.add_parser("configurar", help="assistente no terminal: senha do admin e provedor de IA").set_defaults(func=configure)
    p = sub.add_parser("senha", help="redefine a senha de uma conta")
    p.add_argument("usuario", help="nome de usuário da conta")
    p.set_defaults(func=password)
    p = sub.add_parser("diagnostico", help="confere banco, modelos, acervo, segurança e integrações")
    p.add_argument("--completo", action="store_true", help="também carrega os modelos e faz uma chamada de teste")
    p.set_defaults(func=doctor)
    p = sub.add_parser("backup", help="grava um .zip com banco, contas, ajustes e arquivos enviados")
    p.add_argument("--saida", help="caminho do arquivo .zip")
    p.set_defaults(func=backup)
    p = sub.add_parser("restaurar", help="restaura um backup na pasta de dados (com o Nexo fechado)")
    p.add_argument("arquivo", help="arquivo .zip gerado pelo backup")
    p.add_argument("--substituir", action="store_true", help="guarda a pasta de dados atual numa cópia e restaura por cima")
    p.set_defaults(func=restore)
    p = sub.add_parser("reindexar", help="reindexa documentos (com o Nexo fechado)")
    grupo = p.add_mutually_exclusive_group()
    grupo.add_argument("--desatualizados", action="store_true", help="só os indexados com outra configuração")
    grupo.add_argument("--todos", action="store_true", help="o acervo inteiro")
    p.set_defaults(func=reindex)
    p = sub.add_parser("base-de-teste", help="cria a Base de teste com arquivos de exemplo e o Agente de teste")
    p.add_argument("--conta", default="admin", help="conta registrada como dona da base (padrão: admin)")
    p.set_defaults(func=sample_base)
    sub.add_parser("contas", help="lista as contas de acesso").set_defaults(func=accounts)
    sub.add_parser("versao", help="mostra a versão").set_defaults(func=version)
    p = sub.add_parser("verificar", help="confere o pacote do aplicativo: módulos, servidor, indexação e resposta")
    p.add_argument("--saida", help="grava o relatório neste arquivo")
    p.set_defaults(func=check)
    return root


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    (getattr(args, "func", None) or window)(args)
