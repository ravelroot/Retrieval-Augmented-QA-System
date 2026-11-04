from __future__ import annotations

import json
import logging

from nexo import context, db

log = logging.getLogger("nexo.audit")

ACTIONS = {
    "auth.login": "Entrou",
    "auth.login_failed": "Tentativa de entrada recusada",
    "auth.register": "Criou a própria conta",
    "auth.password": "Trocou a senha",
    "auth.revoke": "Encerrou as outras sessões",
    "user.create": "Criou uma conta",
    "user.role": "Mudou o perfil de uma conta",
    "user.password": "Redefiniu a senha de uma conta",
    "user.delete": "Excluiu uma conta",
    "base.create": "Criou uma base",
    "base.update": "Alterou uma base",
    "base.delete": "Excluiu uma base",
    "base.sample": "Criou a base de teste",
    "document.upload": "Enviou arquivos",
    "document.link": "Importou um link",
    "document.refetch": "Atualizou um link",
    "document.text": "Criou um texto",
    "document.text_update": "Editou um texto",
    "document.update": "Alterou um documento",
    "document.delete": "Excluiu um documento",
    "document.bulk": "Ação em lote em documentos",
    "bot.create": "Criou um agente",
    "bot.update": "Alterou um agente",
    "bot.duplicate": "Duplicou um agente",
    "bot.delete": "Excluiu um agente",
    "key.create": "Criou uma chave de API",
    "key.delete": "Revogou uma chave de API",
    "webhook.create": "Criou um webhook",
    "webhook.update": "Alterou um webhook",
    "webhook.delete": "Excluiu um webhook",
    "channel.create": "Criou uma conexão do WhatsApp",
    "channel.update": "Alterou uma conexão do WhatsApp",
    "channel.delete": "Excluiu uma conexão do WhatsApp",
    "reply.create": "Criou uma resposta pronta",
    "reply.update": "Alterou uma resposta pronta",
    "reply.delete": "Excluiu uma resposta pronta",
    "settings.update": "Alterou os ajustes",
    "settings.reset": "Restaurou os ajustes padrão",
    "maintenance.run": "Rodou uma manutenção",
    "system.backup": "Baixou um backup",
}


def record(action: str, target_type: str | None = None, target_id: str | None = None,
           detail: dict | list | str | None = None, actor: str | None = None) -> None:
    who = actor or "sistema"
    text = detail if detail is None or isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, default=str)
    try:
        with db.session() as s:
            s.add(db.AuditRow(actor=who[:32], action=action[:40], target_type=target_type, target_id=target_id,
                              detail=text[:4000] if text else None, ip=context.client_ip.get(), created_at=db.utcnow()))
            s.commit()
    except Exception:
        log.exception("Falha ao registrar a atividade %s", action)


def label(action: str) -> str:
    return ACTIONS.get(action, action)
