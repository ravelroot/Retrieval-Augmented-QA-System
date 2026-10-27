import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, type ApiKey, type Webhook, type WebhookEvent } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { useToast } from "../components/Toast";
import { formatDateTime } from "../format";

const EVENTS: { name: WebhookEvent; label: string }[] = [
  { name: "document.ready", label: "Documento pronto" },
  { name: "document.failed", label: "Falha na indexação" },
  { name: "question.unanswered", label: "Pergunta sem resposta" },
  { name: "feedback.negative", label: "Resposta avaliada como “não ajudou”" },
];

type Lang = "curl" | "python" | "javascript";

function snippet(lang: Lang, origin: string, key: string): string {
  const k = key || "nxk_SUA_CHAVE";
  if (lang === "curl") {
    return `curl -X POST ${origin}/api/ask \\
  -H "X-API-Key: ${k}" \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Qual o torque dos parafusos da tampa?"}'`;
  }
  if (lang === "python") {
    return `import requests

resposta = requests.post(
    "${origin}/api/ask",
    headers={"X-API-Key": "${k}"},
    json={"question": "Qual o torque dos parafusos da tampa?"},
    timeout=120,
).json()

print(resposta["answer"])
for fonte in resposta["sources"]:
    print(f'[{fonte["rank"]}] {fonte["document_title"]}, página {fonte["page"]}')`;
  }
  return `const resposta = await fetch("${origin}/api/ask", {
  method: "POST",
  headers: { "X-API-Key": "${k}", "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Qual o torque dos parafusos da tampa?" }),
}).then((r) => r.json());

console.log(resposta.answer);
resposta.sources.forEach((f) => console.log(\`[\${f.rank}] \${f.document_title}, página \${f.page}\`));`;
}

function CopyButton({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="ghost-button small" onClick={() => {
      navigator.clipboard.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); }).catch(() => undefined);
    }}>
      <Icon name={done ? "check" : "copy"} size={15} />
      {done ? "Copiado" : label}
    </button>
  );
}

function Keys({ onNewKey }: { onNewKey: (key: string) => void }) {
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiKey | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);

  const load = () => api.keys().then(setKeys).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => { void load(); }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      const key = await api.createKey(name.trim());
      setCreated(key);
      setName("");
      if (key.key) onNewKey(key.key);
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  async function revoke(id: string) {
    try {
      await api.deleteKey(id);
      setConfirm(null);
      toast("Chave revogada. Sistemas que a usavam deixam de ter acesso.");
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  return (
    <div className="box"><section className="panel">
      <h2>Chaves de API</h2>
      <p className="panel__lead">
        Para sistemas externos (intranet, help desk, automações) consultarem o Nexo em seu nome. Envie a chave no cabeçalho
        <code>X-API-Key</code>. Ela tem as mesmas permissões da sua conta.
      </p>
      <form className="inline-form inline-form--wide" onSubmit={create}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome da chave, ex.: Portal de suporte"
          aria-label="Nome da chave" maxLength={80} />
        <button className="primary-button" type="submit" disabled={!name.trim()}><Icon name="key" size={16} />Criar chave</button>
      </form>
      {created?.key && (
        <div className="secret" role="status">
          <p><b>Copie a chave agora.</b> Por segurança, o Nexo guarda só um resumo dela e não consegue mostrá-la de novo.</p>
          <div className="secret__row"><code>{created.key}</code><CopyButton text={created.key} /></div>
        </div>
      )}
      {keys && keys.length > 0 && (
        <table className="table">
          <thead><tr><th>Nome</th><th>Início da chave</th><th>Criada em</th><th>Último uso</th><th><span className="sr-only">Ações</span></th></tr></thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td><code>{k.prefix}…</code></td>
                <td>{formatDateTime(k.created_at)}</td>
                <td>{k.last_used_at ? formatDateTime(k.last_used_at) : "Nunca usada"}</td>
                <td className="table__actions">
                  {confirm === k.id ? (
                    <>
                      <button className="danger-button small" onClick={() => revoke(k.id)}>Revogar</button>
                      <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                    </>
                  ) : (
                    <button className="link-button link-button--danger" onClick={() => setConfirm(k.id)}>Revogar</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {keys && keys.length === 0 && <p className="panel__lead">Nenhuma chave criada.</p>}
    </section></div>
  );
}

function Webhooks() {
  const toast = useToast();
  const [hooks, setHooks] = useState<Webhook[] | null>(null);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<WebhookEvent[]>(["document.ready", "question.unanswered"]);
  const [created, setCreated] = useState<Webhook | null>(null);
  const [testing, setTesting] = useState<string | null>(null);

  const load = () => api.webhooks().then(setHooks).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => { void load(); }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      setCreated(await api.createWebhook(url.trim(), events, null));
      setUrl("");
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  async function test(id: string) {
    setTesting(id);
    try {
      const r = await api.testWebhook(id);
      if (r.status && r.status < 300) toast(`Entrega de teste aceita (HTTP ${r.status}).`);
      else toast(r.error ?? `O destino respondeu HTTP ${r.status}.`, "error");
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setTesting(null);
    }
  }

  async function run(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      toast(done);
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  return (
    <div className="box"><section className="panel">
      <h2>Webhooks</h2>
      <p className="panel__lead">
        O Nexo avisa outro sistema (Slack via automação, Teams, n8n, Zapier, seu backend) quando algo acontece. Cada entrega é um
        POST em JSON assinado com HMAC SHA-256 no cabeçalho <code>X-Nexo-Signature</code>.
      </p>
      <form className="hook-form" onSubmit={create}>
        <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://exemplo.com/nexo/eventos"
          aria-label="Endereço do webhook" required />
        <fieldset>
          <legend>Avisar quando</legend>
          {EVENTS.map((ev) => (
            <label key={ev.name} className="check">
              <input type="checkbox" checked={events.includes(ev.name)}
                onChange={(e) => setEvents(e.target.checked ? [...events, ev.name] : events.filter((x) => x !== ev.name))} />
              <span>{ev.label}</span>
              <small><code>{ev.name}</code></small>
            </label>
          ))}
        </fieldset>
        <button className="primary-button" type="submit" disabled={!url.trim() || !events.length}>
          <Icon name="hook" size={16} />Adicionar webhook
        </button>
      </form>
      {created?.secret && (
        <div className="secret" role="status">
          <p><b>Segredo de assinatura.</b> Use-o no destino para conferir o cabeçalho <code>X-Nexo-Signature</code>. Ele não aparece de novo.</p>
          <div className="secret__row"><code>{created.secret}</code><CopyButton text={created.secret} /></div>
        </div>
      )}
      {hooks && hooks.length > 0 && (
        <ul className="hooks">
          {hooks.map((h) => (
            <li key={h.id} className={h.active ? "" : "is-off"}>
              <div className="hooks__main">
                <code className="hooks__url">{h.url}</code>
                <span className="hooks__events">{h.events.map((e) => EVENTS.find((x) => x.name === e)?.label ?? e).join(", ")}</span>
                <span className="hooks__status">
                  {!h.active ? "Pausado" : h.last_delivery_at
                    ? h.last_status && h.last_status < 300
                      ? <span className="ok">Última entrega aceita (HTTP {h.last_status}) em {formatDateTime(h.last_delivery_at)}</span>
                      : <span className="bad">Última entrega falhou{h.last_status ? ` (HTTP ${h.last_status})` : ""}: {h.last_error ?? "sem detalhes"}</span>
                    : "Nenhuma entrega ainda"}
                </span>
              </div>
              <div className="hooks__actions">
                <button className="ghost-button small" onClick={() => test(h.id)} disabled={testing === h.id}>
                  <Icon name="bolt" size={15} />{testing === h.id ? "Enviando…" : "Testar"}
                </button>
                <button className="icon-button" title={h.active ? "Pausar" : "Retomar"} aria-label={h.active ? "Pausar webhook" : "Retomar webhook"}
                  onClick={() => run(() => api.toggleWebhook(h.id, !h.active), h.active ? "Webhook pausado." : "Webhook retomado.")}>
                  <Icon name={h.active ? "pause" : "play"} size={16} />
                </button>
                <button className="icon-button" title="Excluir" aria-label="Excluir webhook"
                  onClick={() => run(() => api.deleteWebhook(h.id), "Webhook excluído.")}>
                  <Icon name="trash" size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section></div>
  );
}

export function IntegrationsPage() {
  const { user } = useAuth();
  const [lang, setLang] = useState<Lang>("curl");
  const [key, setKey] = useState("");
  const origin = window.location.origin;
  const code = snippet(lang, origin, key);

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Gestão</span>
          <h1>Integrações</h1>
          <p className="page__lead">Leve as respostas com fonte para outros sistemas: chaves de API, uma rota de pergunta direta e avisos por webhook.</p>
        </div>
      </header>

      <Keys onNewKey={setKey} />

      <div className="box"><section className="panel">
        <h2>Pergunta direta</h2>
        <p className="panel__lead">
          <code>POST /api/ask</code> responde sem abrir conversa e devolve a resposta, as fontes com página e as notas de relevância.
          Envie <code>conversation_id</code> para manter o histórico e <code>document_ids</code> para limitar o escopo.
        </p>
        <div className="codebox">
          <div className="codebox__bar">
            <div className="segmented" role="tablist" aria-label="Linguagem">
              {(["curl", "python", "javascript"] as Lang[]).map((l) => (
                <button key={l} role="tab" aria-selected={lang === l} onClick={() => setLang(l)}>
                  {l === "curl" ? "curl" : l === "python" ? "Python" : "JavaScript"}
                </button>
              ))}
            </div>
            <CopyButton text={code} />
          </div>
          <pre><code>{code}</code></pre>
        </div>
        <p className="panel__lead">
          Referência completa e teste das rotas em <a href="/api/docs" target="_blank" rel="noreferrer">/api/docs</a>.
          A conversa também pode ser exportada em Markdown ou JSON pelo botão de download no topo de cada conversa.
        </p>
      </section></div>

      {user?.role === "admin" ? <Webhooks /> : (
        <div className="box"><section className="panel">
          <h2>Webhooks</h2>
          <p className="panel__lead">Só administradores configuram webhooks. Peça a um administrador se precisar de avisos automáticos.</p>
        </section></div>
      )}
    </div>
  );
}
