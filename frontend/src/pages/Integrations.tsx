import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, api, type ApiKey, type Bot, type KeyScope, type OpenAiModel, type Webhook, type WebhookEvent, type Widget } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { useToast } from "../components/Toast";
import { formatDateTime } from "../format";

const EVENTS: { name: WebhookEvent; label: string }[] = [
  { name: "document.ready", label: "Documento pronto" },
  { name: "document.failed", label: "Falha na indexação" },
  { name: "question.unanswered", label: "Pergunta sem resposta" },
  { name: "feedback.negative", label: "Resposta avaliada como “não ajudou”" },
  { name: "whatsapp.message", label: "Nova mensagem no WhatsApp" },
  { name: "whatsapp.handoff", label: "Cliente aguardando atendente" },
];

type Lang = "curl" | "python" | "javascript";

const SCOPES: { id: KeyScope; label: string; hint: string }[] = [
  { id: "full", label: "Completa", hint: "As mesmas permissões da sua conta." },
  { id: "ask", label: "Só consulta", hint: "Perguntar, buscar, abrir conversas e listar agentes e bases." },
  { id: "feed", label: "Só alimentar bases", hint: "Enviar arquivos, textos e links, atualizar e remover itens." },
];

const EXPIRES: { days: number | null; label: string }[] = [
  { days: null, label: "Sem validade" },
  { days: 30, label: "30 dias" },
  { days: 90, label: "90 dias" },
  { days: 365, label: "1 ano" },
];

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

const EMPTY_WIDGET = { name: "", bot_id: "", origins: "", title: "", welcome: "", color: "#000000", position: "right" as "right" | "left",
  show_sources: true };

function lines(text: string): string[] {
  return text.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean);
}

function preview(key: string): void {
  if (document.querySelector(`script[data-nexo="${key}"]`)) {
    (window as unknown as { NexoWidget?: { open: () => void } }).NexoWidget?.open();
    return;
  }
  const script = document.createElement("script");
  script.src = `${window.location.origin}/widget.js`;
  script.async = true;
  script.setAttribute("data-nexo", key);
  script.setAttribute("data-open", "true");
  document.body.appendChild(script);
}

function Widgets({ admin }: { admin: boolean }) {
  const toast = useToast();
  const [params] = useSearchParams();
  const [items, setItems] = useState<Widget[] | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [form, setForm] = useState(EMPTY_WIDGET);
  const [creating, setCreating] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [sites, setSites] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);

  const load = () => api.widgets().then(setItems).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => {
    void load();
    api.bots().then((list) => {
      setBots(list);
      const wanted = params.get("widget");
      const bot = list.find((b) => b.id === wanted) ?? list[0];
      if (bot) setForm((f) => ({ ...f, bot_id: bot.id, name: f.name || `Site · ${bot.name}`, color: bot.color || f.color }));
      if (wanted && list.some((b) => b.id === wanted)) setCreating(true);
    }).catch(() => undefined);
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    try {
      const out = await api.createWidget({ name: form.name.trim(), bot_id: form.bot_id, origins: lines(form.origins), title: form.title.trim() || null,
        welcome: form.welcome.trim() || null, color: form.color, position: form.position, show_sources: form.show_sources });
      toast(`Widget criado. Copie o código e cole no site, antes de </body>.`);
      setCreating(false);
      setForm({ ...EMPTY_WIDGET, bot_id: form.bot_id });
      setItems((list) => [...(list ?? []), out]);
    } catch (err) {
      const apiError = err as ApiError;
      setErrors(Object.keys(apiError.fields ?? {}).length ? apiError.fields : { form: apiError.message });
    }
  }

  async function run(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      toast(done);
      setConfirm(null);
      setEditing(null);
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  const botName = (id: string) => bots.find((b) => b.id === id)?.name ?? "agente";
  return (
    <div className="box" id="widget"><section className="panel">
      <div className="ops-head">
        <div>
          <h2>Widget para sites</h2>
          <p className="panel__lead">
            Coloque um agente no seu site com uma linha de código: aparece um botão de conversa no canto da página, que responde com a
            base do agente e mostra as fontes. Cole o código antes de <code>&lt;/body&gt;</code> no site, no WordPress (rodapé ou um
            plugin de scripts), no Wix ou no Google Tag Manager. Informe os sites autorizados para que só eles usem o widget.
          </p>
        </div>
        {admin && !creating && (
          <button className="primary-button small" onClick={() => setCreating(true)} disabled={!bots.length}>
            <Icon name="plus" size={15} />Novo widget
          </button>
        )}
      </div>
      {admin && !bots.length && <p className="panel__lead">Crie um agente antes de publicar um widget.</p>}
      {!admin && <p className="panel__lead">Só administradores publicam widgets.</p>}
      {creating && (
        <form className="widget-form" onSubmit={create} noValidate>
          <div className="field">
            <label htmlFor="w-name">Nome</label>
            <input id="w-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={80} />
            {errors.name && <p className="field__message">{errors.name}</p>}
          </div>
          <div className="field">
            <label htmlFor="w-bot">Agente que responde</label>
            <select id="w-bot" value={form.bot_id} onChange={(e) => setForm({ ...form, bot_id: e.target.value })}>
              {bots.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.base_name}</option>)}
            </select>
          </div>
          <div className="field field--full">
            <label htmlFor="w-sites">Sites autorizados</label>
            <textarea id="w-sites" rows={2} value={form.origins} onChange={(e) => setForm({ ...form, origins: e.target.value })}
              placeholder={"www.suaempresa.com.br\n*.suaempresa.com.br"} />
            <p className={errors.origins ? "field__message" : "field__hint"}>{errors.origins ?? "Um por linha. *.dominio libera todos os subdomínios. Vazio deixa qualquer site usar."}</p>
          </div>
          <div className="field">
            <label htmlFor="w-title">Título no topo</label>
            <input id="w-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder={botName(form.bot_id)} maxLength={80} />
          </div>
          <div className="field">
            <label htmlFor="w-color">Cor</label>
            <div className="widget-form__row">
              <input id="w-color" type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
              <select aria-label="Posição" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value as "right" | "left" })}>
                <option value="right">Canto direito</option>
                <option value="left">Canto esquerdo</option>
              </select>
            </div>
          </div>
          <div className="field field--full">
            <label htmlFor="w-welcome">Mensagem de boas-vindas</label>
            <textarea id="w-welcome" rows={2} value={form.welcome} onChange={(e) => setForm({ ...form, welcome: e.target.value })}
              placeholder="Vazio usa a saudação do agente." maxLength={500} />
          </div>
          <label className="check field--full">
            <input type="checkbox" checked={form.show_sources} onChange={(e) => setForm({ ...form, show_sources: e.target.checked })} />
            <span>Mostrar as fontes (documento e página) abaixo de cada resposta</span>
          </label>
          {errors.form && <p className="alert field--full" role="alert">{errors.form}</p>}
          <span className="panel__actions field--full">
            <button className="primary-button" type="submit" disabled={!form.name.trim() || !form.bot_id}><Icon name="globe" size={16} />Criar widget</button>
            <button className="ghost-button" type="button" onClick={() => { setCreating(false); setErrors({}); }}>Cancelar</button>
          </span>
        </form>
      )}
      {items && items.length > 0 && (
        <ul className="widgets">
          {items.map((w) => (
            <li key={w.id} className={w.active ? "" : "is-off"}>
              <div className="widgets__top">
                <div>
                  <strong><span className="widgets__dot" style={{ background: w.color }} />{w.name}</strong>
                  <span className="widgets__meta">
                    {w.bot_name ?? "Agente excluído"} · {w.active ? "No ar" : "Pausado"} · {w.questions.toLocaleString("pt-BR")} pergunta(s)
                    {w.unanswered ? `, ${w.unanswered.toLocaleString("pt-BR")} sem resposta` : ""}
                    {w.last_used_at ? ` · último uso ${formatDateTime(w.last_used_at)}` : " · ainda sem uso"}
                  </span>
                </div>
                <div className="widgets__actions">
                  <button className="ghost-button small" onClick={() => preview(w.public_key)} disabled={!w.active}><Icon name="play" size={15} />Testar aqui</button>
                  {w.can_edit && (
                    <button className="icon-button" title={w.active ? "Pausar" : "Retomar"} aria-label={w.active ? "Pausar widget" : "Retomar widget"}
                      onClick={() => run(() => api.updateWidget(w.id, { active: !w.active }), w.active ? "Widget pausado: o botão some dos sites." : "Widget no ar de novo.")}>
                      <Icon name={w.active ? "pause" : "play"} size={16} />
                    </button>
                  )}
                </div>
              </div>
              <div className="codebox">
                <div className="codebox__bar"><span className="muted">Cole no site, antes de &lt;/body&gt;</span><CopyButton text={w.snippet} label="Copiar código" /></div>
                <pre><code>{w.snippet}</code></pre>
              </div>
              {editing === w.id ? (
                <form className="inline-form" onSubmit={(e) => { e.preventDefault(); void run(() => api.updateWidget(w.id, { origins: lines(sites) }), "Sites autorizados atualizados."); }}>
                  <textarea rows={2} className="toolbar__search" value={sites} onChange={(e) => setSites(e.target.value)} aria-label="Sites autorizados" />
                  <button className="primary-button small" type="submit">Salvar</button>
                  <button className="ghost-button small" type="button" onClick={() => setEditing(null)}>Cancelar</button>
                </form>
              ) : (
                <p className="widgets__meta">
                  {w.origins.length ? <>Sites autorizados: {w.origins.map((o, i) => <span key={o}>{i ? " " : ""}<code>{o}</code></span>)}</>
                    : <span className="bad">Qualquer site pode usar este widget. Informe os sites autorizados.</span>}
                  {w.can_edit && <> · <button className="link-button" onClick={() => { setEditing(w.id); setSites(w.origins.join("\n")); }}>editar sites</button></>}
                </p>
              )}
              {w.can_edit && (
                <div className="widgets__actions">
                  {confirm === `rotate-${w.id}` ? (
                    <>
                      <span className="doc__confirm">Os sites com o código antigo param de mostrar o widget. Continuar?</span>
                      <button className="danger-button small" onClick={() => run(() => api.rotateWidget(w.id), "Chave trocada. Atualize o código nos sites.")}>Trocar chave</button>
                      <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                    </>
                  ) : confirm === `delete-${w.id}` ? (
                    <>
                      <span className="doc__confirm">Excluir o widget? O botão some dos sites.</span>
                      <button className="danger-button small" onClick={() => run(() => api.deleteWidget(w.id), "Widget excluído.")}>Excluir</button>
                      <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                    </>
                  ) : (
                    <>
                      <button className="link-button" onClick={() => setConfirm(`rotate-${w.id}`)}>Trocar a chave</button>
                      <button className="link-button link-button--danger" onClick={() => setConfirm(`delete-${w.id}`)}>Excluir</button>
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {items && items.length === 0 && !creating && <p className="panel__lead">Nenhum widget publicado.</p>}
    </section></div>
  );
}

type OaLang = "python" | "javascript" | "curl" | "n8n";

const OA_LANGS: { id: OaLang; label: string }[] = [
  { id: "python", label: "Python" },
  { id: "javascript", label: "JavaScript" },
  { id: "curl", label: "curl" },
  { id: "n8n", label: "n8n e outras" },
];

function oaSnippet(lang: OaLang, base: string, key: string, model: string): string {
  const k = key || "nxk_SUA_CHAVE";
  if (lang === "python") {
    return `from openai import OpenAI

cliente = OpenAI(base_url="${base}", api_key="${k}")
resposta = cliente.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "Como faço a troca do filtro?"}],
)
print(resposta.choices[0].message.content)`;
  }
  if (lang === "javascript") {
    return `import OpenAI from "openai";

const cliente = new OpenAI({ baseURL: "${base}", apiKey: "${k}" });
const resposta = await cliente.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "Como faço a troca do filtro?" }],
});
console.log(resposta.choices[0].message.content);`;
  }
  if (lang === "curl") {
    return `curl ${base}/chat/completions \\
  -H "Authorization: Bearer ${k}" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "${model}", "messages": [{"role": "user", "content": "Como faço a troca do filtro?"}]}'`;
  }
  return `Credencial do tipo OpenAI (n8n, Typebot, Flowise, Dify, Open WebUI, LibreChat, LangChain):

  Base URL / API Base:  ${base}
  API Key:              ${k}
  Modelo:               ${model}

No n8n: Credentials > New > OpenAI, preencha a chave e o Base URL,
e escolha o modelo no nó "OpenAI Chat Model".`;
}

function OpenAiCompat({ apiKey }: { apiKey: string }) {
  const [models, setModels] = useState<OpenAiModel[] | null>(null);
  const [model, setModel] = useState("nexo");
  const [lang, setLang] = useState<OaLang>("python");
  const base = `${window.location.origin}/v1`;
  useEffect(() => {
    api.openaiModels().then((list) => { setModels(list); if (list[1]) setModel(list[1].id); }).catch(() => setModels([]));
  }, []);
  const code = oaSnippet(lang, base, apiKey, model);
  return (
    <div className="box" id="openai"><section className="panel">
      <h2>API compatível com OpenAI</h2>
      <p className="panel__lead">
        Qualquer ferramenta que conversa com a API da OpenAI passa a usar os agentes do Nexo, sem plugin: n8n, Make, Typebot, Flowise,
        Dify, Open WebUI, LibreChat, LangChain e os SDKs oficiais. Cada agente vira um modelo, e <code>nexo</code> consulta o acervo
        inteiro. As respostas seguem presas à base do agente, com as fontes no fim do texto e no campo <code>nexo.sources</code>.
        Use uma chave de API com permissão <b>Só consulta</b>.
      </p>
      <dl className="config">
        <div><dt>Base URL</dt><dd><code>{base}</code> <CopyButton text={base} /></dd></div>
        <div><dt>Chave</dt><dd>Uma chave de API do Nexo, em <code>Authorization: Bearer nxk_…</code></dd></div>
        <div><dt>Modelos</dt><dd>
          {models === null ? "Carregando…" : (
            <span className="models-list">
              {models.map((m) => (
                <button key={m.id} type="button" className={`chip${model === m.id ? " chip--on" : ""}`} title={m.description} onClick={() => setModel(m.id)}>
                  <code>{m.id}</code>
                </button>
              ))}
            </span>
          )}
        </dd></div>
        <div><dt>Rotas</dt><dd><code>GET /v1/models</code> e <code>POST /v1/chat/completions</code>, com <code>stream: true</code> opcional</dd></div>
      </dl>
      <div className="codebox">
        <div className="codebox__bar">
          <div className="segmented" role="tablist" aria-label="Exemplo">
            {OA_LANGS.map((l) => <button key={l.id} role="tab" aria-selected={lang === l.id} onClick={() => setLang(l.id)}>{l.label}</button>)}
          </div>
          <CopyButton text={code} />
        </div>
        <pre><code>{code}</code></pre>
      </div>
    </section></div>
  );
}

function Keys({ onNewKey }: { onNewKey: (key: string) => void }) {
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [scope, setScope] = useState<KeyScope>("full");
  const [expires, setExpires] = useState<number | null>(null);
  const [created, setCreated] = useState<ApiKey | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);

  const load = () => api.keys().then(setKeys).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => { void load(); }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      const key = await api.createKey(name.trim(), scope, expires);
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
    <div className="box" id="chaves"><section className="panel">
      <h2>Chaves de API</h2>
      <p className="panel__lead">
        Para sistemas externos (intranet, help desk, automações) consultarem o Nexo em seu nome. Envie a chave no cabeçalho
        <code>X-API-Key</code>. Dê a cada sistema só o que ele precisa: uma chave de consulta não envia arquivos e uma chave de
        alimentação não faz perguntas. Chaves com validade param sozinhas na data escolhida.
      </p>
      <form className="key-form" onSubmit={create}>
        <input className="toolbar__search" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome da chave, ex.: Portal de suporte"
          aria-label="Nome da chave" maxLength={80} />
        <label className="select"><span>Permissão</span>
          <select value={scope} onChange={(e) => setScope(e.target.value as KeyScope)} title={SCOPES.find((x) => x.id === scope)?.hint}>
            {SCOPES.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </label>
        <label className="select"><span>Validade</span>
          <select value={expires ?? ""} onChange={(e) => setExpires(e.target.value ? Number(e.target.value) : null)}>
            {EXPIRES.map((x) => <option key={x.label} value={x.days ?? ""}>{x.label}</option>)}
          </select>
        </label>
        <button className="primary-button" type="submit" disabled={!name.trim()}><Icon name="key" size={16} />Criar chave</button>
      </form>
      <p className="field__hint">{SCOPES.find((x) => x.id === scope)?.hint}</p>
      {created?.key && (
        <div className="secret" role="status">
          <p><b>Copie a chave agora.</b> Por segurança, o Nexo guarda só um resumo dela e não consegue mostrá-la de novo.</p>
          <div className="secret__row"><code>{created.key}</code><CopyButton text={created.key} /></div>
        </div>
      )}
      {keys && keys.length > 0 && (
        <table className="table">
          <thead><tr><th>Nome</th><th>Início da chave</th><th>Permissão</th><th>Validade</th><th>Último uso</th><th><span className="sr-only">Ações</span></th></tr></thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id} className={k.expired ? "is-off" : ""}>
                <td>{k.name}</td>
                <td><code>{k.prefix}…</code></td>
                <td>{SCOPES.find((x) => x.id === k.scope)?.label ?? k.scope}</td>
                <td>{k.expired ? <span className="bad">Venceu em {formatDateTime(k.expires_at)}</span> : k.expires_at ? `Até ${formatDateTime(k.expires_at)}` : "Sem validade"}</td>
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
    <div className="box" id="webhooks"><section className="panel">
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
          <p className="page__lead">Leve os agentes para onde as pessoas estão: um widget no seu site, ferramentas que falam com a API da OpenAI, chaves de API, pergunta direta e avisos por webhook.</p>
        </div>
      </header>

      <nav className="int-nav" aria-label="Seções das integrações">
        <a className="chip" href="#widget">Widget para sites</a>
        <a className="chip" href="#openai">Compatível com OpenAI</a>
        <a className="chip" href="#chaves">Chaves de API</a>
        <a className="chip" href="#direta">Pergunta direta</a>
        <a className="chip" href="#webhooks">Webhooks</a>
        <a className="chip" href="#monitoramento">Monitoramento</a>
      </nav>

      <Widgets admin={user?.role === "admin"} />

      <OpenAiCompat apiKey={key} />

      <Keys onNewKey={setKey} />

      <div className="box" id="direta"><section className="panel">
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

      <div className="box" id="monitoramento"><section className="panel">
        <h2>Monitoramento</h2>
        <p className="panel__lead">
          Rotas para balanceadores, orquestradores e painéis. Toda resposta traz <code>X-Request-ID</code>, o mesmo que aparece nos registros do servidor.
          Perguntas acima do limite por minuto recebem HTTP 429 com <code>Retry-After</code>.
        </p>
        <dl className="config">
          <div><dt><code>GET /api/health</code></dt><dd>Versão, sem autenticação</dd></div>
          <div><dt><code>GET /api/health/ready</code></dt><dd>Confere o banco; responde 503 se ele estiver fora</dd></div>
          <div><dt><code>GET /api/health/metrics</code></dt><dd>Métricas no formato do Prometheus (chave completa de administrador)</dd></div>
          <div><dt><code>NEXO_CORS_ORIGINS</code></dt><dd>Libera sites que chamam a API direto do navegador, separados por vírgula</dd></div>
        </dl>
      </section></div>

      {user?.role === "admin" ? <Webhooks /> : (
        <div className="box" id="webhooks"><section className="panel">
          <h2>Webhooks</h2>
          <p className="panel__lead">Só administradores configuram webhooks. Peça a um administrador se precisar de avisos automáticos.</p>
        </section></div>
      )}
    </div>
  );
}
