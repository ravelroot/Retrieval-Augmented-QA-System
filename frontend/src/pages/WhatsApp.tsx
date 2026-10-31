import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ApiError, api, type Bot, type Channel, type ChannelInput, type ChannelStatus, type Contact, type ContactDetail,
  type ContactFilter, type Provider, type WaMessage, type WaSummary,
} from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { SourceSlip } from "../components/SourceSlip";
import { useToast } from "../components/Toast";
import { formatDateTime, formatRelative, plural } from "../format";

const FILTERS: { id: ContactFilter; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "unread", label: "Não lidas" },
  { id: "waiting", label: "Aguardando atendente" },
  { id: "bot", label: "Com o agente" },
  { id: "human", label: "Com pessoas" },
];

const STATUS: Record<WaMessage["status"], string> = {
  received: "recebida",
  pending: "enviando",
  sent: "enviada",
  delivered: "entregue",
  read: "lida",
  failed: "falhou",
};

const STATE: Record<ChannelStatus["state"], { label: string; cls: string }> = {
  open: { label: "Conectado", cls: "on" },
  connecting: { label: "Conectando", cls: "wait" },
  close: { label: "Desconectado", cls: "off" },
  unknown: { label: "Sem verificação", cls: "off" },
};

const PROVIDERS: { id: Provider; title: string; lead: string; detail: string }[] = [
  { id: "evolution", title: "Seu número por QR code", lead: "Evolution API", detail: "Conecte o WhatsApp que você já usa lendo um QR code. Precisa da Evolution API instalada por você (Docker)." },
  { id: "cloud", title: "API oficial da Meta", lead: "WhatsApp Cloud API", detail: "Número comercial verificado na Meta. Mais estável para alto volume; respostas livres até 24 h após a última mensagem do cliente." },
  { id: "simulador", title: "Simulador", lead: "Sem número real", detail: "Teste o agente e a caixa de entrada simulando mensagens de clientes. Nada é enviado de verdade." },
];

const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });

function when(value: string) {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return time.format(d);
}

function phoneLabel(p: string) {
  const d = p.replace(/\D/g, "");
  if (d.length === 13 && d.startsWith("55")) return `+55 (${d.slice(2, 4)}) ${d.slice(4, 9)}-${d.slice(9)}`;
  if (d.length === 12 && d.startsWith("55")) return `+55 (${d.slice(2, 4)}) ${d.slice(4, 8)}-${d.slice(8)}`;
  return d ? `+${d}` : p;
}

function initials(c: Contact) {
  const base = (c.name ?? "").trim();
  if (!base) return c.phone.slice(-2);
  return base.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
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

function Bubble({ m }: { m: WaMessage }) {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const author = m.direction === "in" ? "Cliente" : m.author === "agente" ? "Agente" : m.author === "celular" ? "Pelo celular"
    : m.author === user?.username ? `Você (${user.name})` : m.author;
  return (
    <div className={`wa-msg wa-msg--${m.direction}${m.author === "agente" ? " wa-msg--bot" : ""}${m.status === "failed" ? " wa-msg--failed" : ""}`}>
      <div className="wa-msg__bubble">
        {m.direction === "out" && <span className="wa-msg__author">{m.author === "agente" && <Icon name="bot" size={13} />}{author}</span>}
        <p>{m.body}</p>
        <span className="wa-msg__meta">
          {when(m.created_at)}
          {m.direction === "out" && <> · {STATUS[m.status]}</>}
          {m.answered === false && <> · sem base nos documentos</>}
        </span>
        {m.error && <span className="wa-msg__error">{m.error}</span>}
      </div>
      {m.sources.length > 0 && (
        <div className="wa-msg__sources">
          <button className="link-button" onClick={() => setOpen(!open)}>
            {open ? "Esconder trechos" : `Ver ${plural(m.sources.length, "trecho", "trechos")}`}
          </button>
          {open && (
            <ol className="results__list">
              {m.sources.map((s) => <li key={s.rank}><SourceSlip source={s} query="" onError={() => undefined} /></li>)}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

function Simulator({ channel, onSent }: { channel: Channel; onSent: (contactId: string) => void }) {
  const toast = useToast();
  const [phone, setPhone] = useState("5521999990001");
  const [name, setName] = useState("Cliente de teste");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || !phone.trim()) return;
    setBusy(true);
    try {
      const r = await api.simulate(channel.id, phone.trim(), name.trim(), text.trim());
      setText("");
      onSent(r.contact_id);
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="wa-sim" onSubmit={send}>
      <strong><Icon name="sparkle" size={15} />Simular mensagem de cliente</strong>
      <div className="wa-sim__row">
        <input value={phone} onChange={(e) => setPhone(e.target.value)} aria-label="Telefone do cliente" placeholder="Telefone" />
        <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Nome do cliente" placeholder="Nome" />
      </div>
      <div className="wa-sim__row">
        <input value={text} onChange={(e) => setText(e.target.value)} aria-label="Mensagem do cliente" placeholder="Ex.: Qual o horário de atendimento?" />
        <button className="primary-button small" type="submit" disabled={busy || !text.trim()}>Receber</button>
      </div>
    </form>
  );
}

function Inbox({ channels, bots, onSetup }: { channels: Channel[]; bots: Bot[]; onSetup: () => void }) {
  const toast = useToast();
  const [channelId, setChannelId] = useState(channels[0]?.id ?? "");
  const [filter, setFilter] = useState<ContactFilter>("all");
  const [q, setQ] = useState("");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ContactDetail | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [summary, setSummary] = useState<WaSummary | null>(null);
  const [pane, setPane] = useState<"list" | "chat">("list");
  const bottom = useRef<HTMLDivElement>(null);
  const channel = channels.find((c) => c.id === channelId) ?? channels[0];
  const bot = bots.find((b) => b.id === channel?.bot_id) ?? null;

  useEffect(() => {
    if (!channels.find((c) => c.id === channelId) && channels[0]) setChannelId(channels[0].id);
  }, [channels, channelId]);

  const loadContacts = useCallback(() => {
    if (!channel) return;
    api.contacts(channel.id, filter, q).then(setContacts).catch(() => undefined);
    api.waSummary().then(setSummary).catch(() => undefined);
  }, [channel?.id, filter, q]);

  const loadDetail = useCallback(() => {
    if (!openId) return;
    api.contact(openId).then((d) => setDetail((prev) => {
      if (prev && prev.id === d.id && prev.messages.length === d.messages.length && prev.bot_enabled === d.bot_enabled
        && prev.needs_human === d.needs_human && prev.messages.at(-1)?.status === d.messages.at(-1)?.status) return prev;
      return d;
    })).catch(() => undefined);
  }, [openId]);

  useEffect(() => { loadContacts(); }, [loadContacts]);
  useEffect(() => { setDetail(null); loadDetail(); }, [openId]);
  useEffect(() => {
    const timer = window.setInterval(() => { loadContacts(); loadDetail(); }, 3000);
    return () => window.clearInterval(timer);
  }, [loadContacts, loadDetail]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [detail?.messages.length, detail?.id]);

  function openContact(id: string) {
    setOpenId(id);
    setPane("chat");
    setText("");
  }

  async function send(e?: FormEvent) {
    e?.preventDefault();
    if (!detail || !text.trim() || sending) return;
    setSending(true);
    try {
      const m = await api.sendToContact(detail.id, text.trim());
      setDetail({ ...detail, bot_enabled: false, needs_human: false, messages: [...detail.messages, m] });
      setText("");
      if (m.status === "failed") toast(m.error ?? "O WhatsApp recusou a mensagem.", "error");
      loadContacts();
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setSending(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  }

  async function suggest() {
    if (!detail) return;
    setSuggesting(true);
    try {
      const s = await api.suggest(detail.id);
      setText(s.text);
      if (!s.answered) toast("O agente não achou isso na base. Revise antes de enviar.", "error");
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setSuggesting(false);
    }
  }

  async function patch(change: { bot_enabled?: boolean; needs_human?: boolean }, done: string) {
    if (!detail) return;
    try {
      const c = await api.updateContact(detail.id, change);
      setDetail({ ...detail, ...c });
      toast(done);
      loadContacts();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  if (!channel) {
    return (
      <div className="box"><section className="panel wa-empty">
        <span className="dropzone__icon"><Icon name="whatsapp" size={22} /></span>
        <h2>Conecte um número para atender clientes</h2>
        <p className="panel__lead">Ligue seu WhatsApp por QR code, pela API oficial da Meta ou teste com o simulador. Um agente pode responder sozinho e você assume quando quiser.</p>
        <button className="primary-button" onClick={onSetup}><Icon name="plus" size={16} />Criar conexão</button>
      </section></div>
    );
  }

  return (
    <>
      <div className="box wa-top">
        <section className="lid wa-lid" aria-label="Resumo do atendimento">
          <div className="wa-lid__main">
            <span className="lid__label">Aguardando atendente</span>
            <strong className="lid__number">{summary?.waiting ?? "—"}</strong>
          </div>
          <dl className="lid__stats">
            <div><dt>Contatos</dt><dd>{summary?.contacts ?? 0}</dd></div>
            <div><dt>Não lidas</dt><dd>{summary?.unread ?? 0}</dd></div>
            <div><dt>Respostas do agente hoje</dt><dd>{summary?.bot_answers_today ?? 0}</dd></div>
            <div><dt>Conexões</dt><dd>{summary?.channels ?? channels.length}</dd></div>
          </dl>
        </section>
      </div>

      <div className={`box wa-inbox wa-inbox--${pane}`}>
        <section className="wa-contacts" aria-label="Contatos">
          {channels.length > 1 && (
            <label className="select wa-channel">
              <span>Conexão</span>
              <select value={channel.id} onChange={(e) => { setChannelId(e.target.value); setOpenId(null); }}>
                {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          )}
          <input className="threads__filter" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar nome ou telefone" aria-label="Buscar contato" />
          <div className="wa-filters" role="tablist" aria-label="Filtros">
            {FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} className={filter === f.id ? "is-on" : ""} onClick={() => setFilter(f.id)}>{f.label}</button>
            ))}
          </div>
          {contacts.length === 0 ? (
            <p className="threads__empty">{q || filter !== "all" ? "Nenhum contato com esse filtro." : "As conversas com clientes aparecem aqui assim que alguém mandar mensagem."}</p>
          ) : (
            <ul className="wa-list">
              {contacts.map((c) => (
                <li key={c.id}>
                  <button className={`wa-contact${c.id === openId ? " is-on" : ""}`} onClick={() => openContact(c.id)}>
                    <span className={`wa-avatar${c.needs_human ? " wa-avatar--wait" : ""}`} aria-hidden="true">{initials(c)}</span>
                    <span className="wa-contact__text">
                      <span className="wa-contact__top">
                        <strong>{c.name || phoneLabel(c.phone)}</strong>
                        {c.last_message_at && <small>{formatRelative(c.last_message_at)}</small>}
                      </span>
                      <span className="wa-contact__last">
                        {c.last_direction === "out" && <Icon name="check" size={13} />}
                        {c.last_message ?? "Sem mensagens"}
                      </span>
                      <span className="wa-contact__tags">
                        {c.needs_human ? <span className="wa-state wa-state--wait">Aguardando atendente</span>
                          : c.bot_enabled ? <span className="wa-state wa-state--bot">Agente</span>
                            : <span className="wa-state">Pessoa</span>}
                        {c.unread > 0 && <span className="wa-unread" aria-label={`${c.unread} não lidas`}>{c.unread}</span>}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {channel.provider === "simulador" && <Simulator channel={channel} onSent={(id) => { loadContacts(); openContact(id); }} />}
        </section>

        <section className="wa-chat" aria-label="Conversa">
          {!detail ? (
            <div className="empty wa-chat__empty">
              <h2>Escolha uma conversa</h2>
              <p>{bot ? `${bot.name} responde sozinho com a base ${bot.base_name}. Você pode assumir qualquer conversa.` : "Nenhum agente nesta conexão: as mensagens esperam por uma pessoa."}</p>
            </div>
          ) : (
            <>
              <header className="wa-chat__head">
                <button className="icon-button wa-back" aria-label="Voltar aos contatos" onClick={() => setPane("list")}><Icon name="arrowLeft" /></button>
                <div className="wa-chat__who">
                  <strong>{detail.name || phoneLabel(detail.phone)}</strong>
                  <small>{phoneLabel(detail.phone)}</small>
                </div>
                <div className="wa-switch" role="group" aria-label="Quem responde">
                  <button aria-pressed={detail.bot_enabled} className={detail.bot_enabled ? "is-on" : ""} disabled={!bot}
                    title={bot ? undefined : "Escolha um agente para esta conexão em Conexões"}
                    onClick={() => !detail.bot_enabled && patch({ bot_enabled: true, needs_human: false }, "O agente voltou a responder este contato.")}>
                    <Icon name="bot" size={15} />Agente respondendo
                  </button>
                  <button aria-pressed={!detail.bot_enabled} className={!detail.bot_enabled ? "is-on" : ""}
                    onClick={() => detail.bot_enabled && patch({ bot_enabled: false }, "Você assumiu a conversa. O agente fica em silêncio aqui.")}>
                    <Icon name="user" size={15} />Você no controle
                  </button>
                </div>
              </header>
              {detail.needs_human && (
                <div className="wa-banner">
                  <span><b>Cliente aguardando atendente.</b> O agente pausou: não achou a resposta na base ou o cliente pediu uma pessoa.</span>
                  <button className="ghost-button small" onClick={() => patch({ needs_human: false }, "Marcado como atendido.")}>Marcar como atendido</button>
                </div>
              )}
              {!detail.bot_enabled && !detail.needs_human && bot && (
                <div className="wa-banner wa-banner--soft">
                  <span>Você está no controle. O agente não responde este contato.</span>
                  <button className="ghost-button small" onClick={() => patch({ bot_enabled: true, needs_human: false }, "O agente voltou a responder este contato.")}>
                    <Icon name="bot" size={15} />Devolver ao agente
                  </button>
                </div>
              )}
              <div className="wa-thread">
                {detail.messages.map((m) => <Bubble key={m.id} m={m} />)}
                <div ref={bottom} />
              </div>
              <form className="wa-composer" onSubmit={send}>
                <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey} rows={2} maxLength={4000}
                  placeholder="Responder como pessoa (Enter envia, Shift + Enter quebra a linha)" aria-label="Resposta" />
                <div className="wa-composer__actions">
                  <button type="button" className="ghost-button small" onClick={suggest} disabled={suggesting || !bot}
                    title={bot ? "O agente redige; você revisa e envia" : "Escolha um agente para esta conexão"}>
                    <Icon name="sparkle" size={15} />{suggesting ? "Pensando…" : "Sugerir resposta"}
                  </button>
                  <button className="send" type="submit" disabled={!text.trim() || sending} aria-label="Enviar resposta"><Icon name="send" /></button>
                </div>
              </form>
            </>
          )}
        </section>

        <aside className="wa-side" aria-label="Detalhes do contato">
          {detail ? (
            <>
              <span className={`wa-avatar wa-avatar--big${detail.needs_human ? " wa-avatar--wait" : ""}`} aria-hidden="true">{initials(detail)}</span>
              <h3>{detail.name || "Sem nome"}</h3>
              <dl className="wa-facts">
                <div><dt>Telefone</dt><dd>{phoneLabel(detail.phone)}</dd></div>
                <div><dt>Conexão</dt><dd>{channel.name}</dd></div>
                <div><dt>Agente</dt><dd>{bot ? <Link to="/agentes">{bot.name}</Link> : "Nenhum"}</dd></div>
                <div><dt>Base</dt><dd>{bot ? <Link to={`/bases/${bot.base_id}`}>{bot.base_name}</Link> : "—"}</dd></div>
                <div><dt>Situação</dt><dd>{detail.needs_human ? "Aguardando atendente" : detail.bot_enabled ? "Com o agente" : "Com uma pessoa"}</dd></div>
                <div><dt>Primeiro contato</dt><dd>{formatDateTime(detail.created_at)}</dd></div>
              </dl>
              <label className="check">
                <input type="checkbox" checked={detail.needs_human}
                  onChange={(e) => patch({ needs_human: e.target.checked }, e.target.checked ? "Marcado como aguardando atendente." : "Marcado como atendido.")} />
                Aguardando atendente
              </label>
            </>
          ) : (
            <p className="panel__lead">Os dados do contato aparecem aqui.</p>
          )}
        </aside>
      </div>
    </>
  );
}

function StatusDot({ channel }: { channel: Channel }) {
  const [status, setStatus] = useState<ChannelStatus | null>(null);
  useEffect(() => {
    let alive = true;
    api.channelStatus(channel.id).then((s) => alive && setStatus(s)).catch(() => alive && setStatus({ state: "unknown", detail: null }));
    return () => { alive = false; };
  }, [channel.id, channel.provider]);
  const s = STATE[status?.state ?? "unknown"];
  return <span className={`wa-dot wa-dot--${status ? s.cls : "off"}`} title={status?.detail ?? undefined}>{status ? s.label : "Verificando…"}</span>;
}

function ChannelForm({ initial, bots, onDone, onCancel }: { initial: Channel | null; bots: Bot[]; onDone: (c: Channel) => void; onCancel: () => void }) {
  const toast = useToast();
  const [provider, setProvider] = useState<Provider>(initial?.provider ?? "evolution");
  const [name, setName] = useState(initial?.name ?? "Atendimento");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [baseUrl, setBaseUrl] = useState(initial?.settings.base_url ?? "http://localhost:8080");
  const [apiKey, setApiKey] = useState("");
  const [instance, setInstance] = useState(initial?.settings.instance ?? "nexo");
  const [phoneNumberId, setPhoneNumberId] = useState(initial?.settings.phone_number_id ?? "");
  const [token, setToken] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [version, setVersion] = useState(initial?.settings.api_version ?? "v24.0");
  const [botId, setBotId] = useState(initial?.bot_id ?? bots[0]?.id ?? "");
  const [auto, setAuto] = useState(initial?.auto_reply ?? true);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const input: ChannelInput = { name: name.trim() || "Atendimento", provider, phone: phone.trim() || null, bot_id: botId || null, auto_reply: auto };
    if (provider === "evolution") Object.assign(input, { base_url: baseUrl.trim(), instance: instance.trim(), ...(apiKey ? { api_key: apiKey } : {}) });
    if (provider === "cloud") Object.assign(input, { phone_number_id: phoneNumberId.trim(), api_version: version.trim() || "v24.0", ...(token ? { access_token: token } : {}), ...(appSecret ? { app_secret: appSecret } : {}) });
    try {
      onDone(initial ? await api.updateChannel(initial.id, input) : await api.createChannel(input));
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="wa-form" onSubmit={submit}>
      <div className="wa-step">
        <span className="wa-step__n">1</span>
        <div className="wa-step__body">
          <h3>Como conectar</h3>
          <div className="wa-providers" role="radiogroup" aria-label="Provedor">
            {PROVIDERS.map((p) => (
              <button key={p.id} type="button" role="radio" aria-checked={provider === p.id}
                className={`wa-provider${provider === p.id ? " is-on" : ""}`} onClick={() => setProvider(p.id)}>
                <small>{p.lead}</small>
                <strong>{p.title}</strong>
                <span>{p.detail}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="wa-step">
        <span className="wa-step__n">2</span>
        <div className="wa-step__body">
          <h3>Identificação e credenciais</h3>
          <div className="wa-grid">
            <label className="kb-field"><span>Nome da conexão</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} /></label>
            <label className="kb-field"><span>Número exibido</span><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="5521999990000" maxLength={32} /></label>
            {provider === "evolution" && (
              <>
                <label className="kb-field"><span>Endereço da Evolution API</span><input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:8080" required /></label>
                <label className="kb-field"><span>Nome da instância</span><input value={instance} onChange={(e) => setInstance(e.target.value)} required /></label>
                <label className="kb-field wa-grid__wide"><span>Chave (apikey)</span>
                  <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off"
                    placeholder={initial?.secrets.api_key ? `Atual: ${initial.secrets.api_key} (vazio mantém)` : "AUTHENTICATION_API_KEY da Evolution"} />
                </label>
              </>
            )}
            {provider === "cloud" && (
              <>
                <label className="kb-field"><span>Phone Number ID</span><input value={phoneNumberId} onChange={(e) => setPhoneNumberId(e.target.value)} required /></label>
                <label className="kb-field"><span>Versão da API</span><input value={version} onChange={(e) => setVersion(e.target.value)} /></label>
                <label className="kb-field"><span>Token de acesso</span>
                  <input type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off"
                    placeholder={initial?.secrets.access_token ? `Atual: ${initial.secrets.access_token} (vazio mantém)` : "Token permanente do usuário do sistema"} />
                </label>
                <label className="kb-field"><span>App secret</span>
                  <input type="password" value={appSecret} onChange={(e) => setAppSecret(e.target.value)} autoComplete="off"
                    placeholder={initial?.secrets.app_secret ? `Atual: ${initial.secrets.app_secret} (vazio mantém)` : "Confere a assinatura dos avisos"} />
                </label>
              </>
            )}
            {provider === "simulador" && <p className="panel__lead wa-grid__wide">O simulador não precisa de credenciais. As mensagens de clientes são criadas pela caixa de entrada.</p>}
          </div>
        </div>
      </div>

      <div className="wa-step">
        <span className="wa-step__n">3</span>
        <div className="wa-step__body">
          <h3>Quem responde</h3>
          {bots.length === 0 ? (
            <p className="panel__lead">Nenhum agente criado. <Link to="/agentes">Crie um agente</Link> para responder sozinho; sem ele, as mensagens esperam por uma pessoa.</p>
          ) : (
            <div className="wa-grid">
              <label className="select"><span>Agente</span>
                <select value={botId} onChange={(e) => setBotId(e.target.value)}>
                  <option value="">Nenhum (só pessoas)</option>
                  {bots.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.base_name}</option>)}
                </select>
              </label>
              <label className="check check--inline"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />Responder automaticamente</label>
            </div>
          )}
        </div>
      </div>

      <div className="kb-form__actions">
        <button className="primary-button" type="submit" disabled={busy}>{initial ? "Salvar conexão" : "Criar conexão"}</button>
        <button className="ghost-button" type="button" onClick={onCancel}>Cancelar</button>
        <span className="kb-hint">O passo 4 (webhook e QR code) aparece depois de salvar.</span>
      </div>
    </form>
  );
}

function Connect({ channel }: { channel: Channel }) {
  const toast = useToast();
  const [publicUrl, setPublicUrl] = useState(window.location.origin);
  const [qr, setQr] = useState<{ state: ChannelStatus["state"]; base64: string | null; pairing_code: string | null } | null>(null);
  const [showQr, setShowQr] = useState(false);
  const [busy, setBusy] = useState(false);
  const url = `${publicUrl.replace(/\/+$/, "")}${channel.webhook_path}`;

  useEffect(() => {
    if (!showQr) return;
    let alive = true;
    const load = () => api.channelQr(channel.id).then((r) => {
      if (!alive) return;
      setQr(r);
      if (r.state === "open") { setShowQr(false); toast("WhatsApp conectado."); }
    }).catch((e: ApiError) => { if (alive) { toast(e.message, "error"); setShowQr(false); } });
    load();
    const timer = window.setInterval(load, 5000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [showQr, channel.id]);

  async function register() {
    setBusy(true);
    try {
      const r = await api.channelWebhook(channel.id, publicUrl.trim());
      if (r.ok) toast(r.detail ?? "Webhook registrado.");
      else toast(r.detail ?? "Não foi possível registrar o webhook.", "error");
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  if (channel.provider === "simulador") {
    return <p className="panel__lead">Simulador pronto. Abra a <b>Caixa de entrada</b> e use “Simular mensagem de cliente”.</p>;
  }

  return (
    <div className="wa-connect">
      <label className="kb-field">
        <span>Endereço público do Nexo</span>
        <input value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)} placeholder="https://nexo.suaempresa.com.br" />
      </label>
      <p className="kb-hint">O WhatsApp precisa alcançar o Nexo. Em teste local, use um túnel (ngrok, Cloudflare Tunnel) e cole o endereço aqui.</p>
      <div className="secret">
        <span>{channel.provider === "cloud" ? "URL de retorno (Callback URL) no painel da Meta" : "URL do webhook"}</span>
        <div className="secret__row"><code>{url}</code><CopyButton text={url} /></div>
        {channel.provider === "cloud" && (
          <>
            <span>Token de verificação (Verify token)</span>
            <div className="secret__row"><code>{channel.verify_token}</code><CopyButton text={channel.verify_token} /></div>
            <span className="kb-hint">No painel da Meta, assine o campo <code>messages</code> do webhook.</span>
          </>
        )}
      </div>
      {channel.provider === "evolution" && (
        <div className="wa-connect__actions">
          <button className="ghost-button" onClick={register} disabled={busy}><Icon name="hook" size={16} />{busy ? "Registrando…" : "Registrar webhook na Evolution"}</button>
          <button className="primary-button" onClick={() => setShowQr(!showQr)}><Icon name="phone" size={16} />{showQr ? "Esconder QR code" : "Mostrar QR code"}</button>
        </div>
      )}
      {showQr && (
        <div className="wa-qr">
          {qr?.base64 ? <img src={qr.base64.startsWith("data:") ? qr.base64 : `data:image/png;base64,${qr.base64}`} alt="QR code para conectar o WhatsApp" /> : <div className="busline" aria-hidden="true"><span /></div>}
          <div>
            <strong>No celular: WhatsApp › Aparelhos conectados › Conectar um aparelho</strong>
            <p className="panel__lead">Aponte a câmera para o código. Ele se renova sozinho a cada 5 s até conectar.</p>
            {qr?.pairing_code && <p>Código de pareamento: <code>{qr.pairing_code}</code></p>}
            {qr && <p className="kb-hint">Situação: {STATE[qr.state].label}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function Connections({ channels, bots, reload, startNew }: { channels: Channel[]; bots: Bot[]; reload: () => void; startNew: boolean }) {
  const { user } = useAuth();
  const toast = useToast();
  const admin = user?.role === "admin";
  const [editing, setEditing] = useState<Channel | "new" | null>(startNew && admin ? "new" : null);
  const [openId, setOpenId] = useState<string | null>(channels[0]?.id ?? null);
  const [confirm, setConfirm] = useState<string | null>(null);

  useEffect(() => { if (startNew && admin) setEditing("new"); }, [startNew, admin]);

  async function run(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      toast(done);
      reload();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  return (
    <div className="wa-conns">
      {!admin && <p className="alert">Só administradores criam e alteram conexões. Você pode atender pela Caixa de entrada.</p>}
      {admin && !editing && (
        <button className="primary-button wa-new" onClick={() => setEditing("new")}><Icon name="plus" size={16} />Nova conexão</button>
      )}
      {editing && (
        <div className="box"><section className="panel">
          <h2>{editing === "new" ? "Nova conexão" : `Editar ${editing.name}`}</h2>
          <ChannelForm initial={editing === "new" ? null : editing} bots={bots} onCancel={() => setEditing(null)}
            onDone={(c) => { setEditing(null); setOpenId(c.id); toast("Conexão salva. Agora conecte o número no passo 4."); reload(); }} />
        </section></div>
      )}
      {channels.length === 0 && !editing && (
        <div className="box"><section className="panel"><p className="panel__lead">Nenhuma conexão ainda.</p></section></div>
      )}
      {channels.map((c) => (
        <div key={c.id} className={`box wa-conn${c.active ? "" : " is-off"}`}>
          <section className="panel">
            <div className="wa-conn__head">
              <div className="wa-conn__title">
                <strong>{c.name}</strong>
                <small>{PROVIDERS.find((p) => p.id === c.provider)?.title}{c.phone ? ` · ${phoneLabel(c.phone)}` : ""}</small>
              </div>
              {c.active ? <StatusDot channel={c} /> : <span className="wa-dot wa-dot--off">Pausada</span>}
              <div className="wa-conn__actions">
                <button className="ghost-button small" onClick={() => setOpenId(openId === c.id ? null : c.id)}>
                  <Icon name="link" size={15} />{openId === c.id ? "Fechar" : "Conectar"}
                </button>
                {admin && (
                  <>
                    <button className="icon-button" title="Editar" aria-label={`Editar ${c.name}`} onClick={() => setEditing(c)}><Icon name="edit" size={16} /></button>
                    <button className="icon-button" title={c.active ? "Pausar" : "Ativar"} aria-label={c.active ? "Pausar conexão" : "Ativar conexão"}
                      onClick={() => run(() => api.updateChannel(c.id, { active: !c.active }), c.active ? "Conexão pausada." : "Conexão ativada.")}>
                      <Icon name={c.active ? "pause" : "play"} size={16} />
                    </button>
                    {confirm === c.id ? (
                      <>
                        <button className="danger-button small" onClick={() => { setConfirm(null); void run(() => api.deleteChannel(c.id), "Conexão excluída."); }}>Excluir</button>
                        <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                      </>
                    ) : (
                      <button className="icon-button" title="Excluir" aria-label={`Excluir ${c.name}`} onClick={() => setConfirm(c.id)}><Icon name="trash" size={16} /></button>
                    )}
                  </>
                )}
              </div>
            </div>
            <dl className="wa-conn__facts">
              <div><dt>Agente</dt><dd>{c.bot_name ?? "Nenhum"}</dd></div>
              <div><dt>Resposta automática</dt><dd>{c.auto_reply && c.bot_id ? "Ligada" : "Desligada"}</dd></div>
              <div><dt>Contatos</dt><dd>{c.contacts}</dd></div>
              <div><dt>Aguardando</dt><dd>{c.waiting}</dd></div>
              <div><dt>Último aviso</dt><dd>{c.last_event_at ? formatDateTime(c.last_event_at) : "Nenhum ainda"}</dd></div>
            </dl>
            {c.last_error && <p className="doc__error">Último erro: {c.last_error}</p>}
            {openId === c.id && (
              <div className="wa-step wa-step--inline">
                <span className="wa-step__n">4</span>
                <div className="wa-step__body"><h3>Ligar o número ao Nexo</h3><Connect channel={c} /></div>
              </div>
            )}
          </section>
        </div>
      ))}
    </div>
  );
}

export function WhatsAppPage() {
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [startNew, setStartNew] = useState(false);
  const tab = params.get("aba") === "conexoes" ? "conexoes" : "entrada";

  const load = useCallback(() => {
    api.channels().then(setChannels).catch((e: ApiError) => { toast(e.message, "error"); setChannels([]); });
  }, [toast]);
  useEffect(() => { load(); api.bots().then(setBots).catch(() => undefined); }, [load]);

  const active = useMemo(() => (channels ?? []).filter((c) => c.active), [channels]);

  function go(next: "entrada" | "conexoes", fresh = false) {
    setStartNew(fresh);
    setParams(next === "conexoes" ? { aba: "conexoes" } : {}, { replace: true });
  }

  return (
    <div className="page page--wide">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Atendimento</span>
          <h1>WhatsApp</h1>
          <p className="page__lead">Fale com clientes pelo seu WhatsApp. O agente responde com a base dele e passa para você quando não souber.</p>
        </div>
        <div className="segmented wa-tabs" role="tablist" aria-label="Seções">
          <button role="tab" aria-selected={tab === "entrada"} onClick={() => go("entrada")}>Caixa de entrada</button>
          <button role="tab" aria-selected={tab === "conexoes"} onClick={() => go("conexoes")}>Conexões</button>
        </div>
      </header>
      {channels === null ? <p className="kb-hint">Carregando…</p>
        : tab === "entrada" ? <Inbox channels={active} bots={bots} onSetup={() => go("conexoes", true)} />
          : <Connections channels={channels} bots={bots} reload={load} startNew={startNew} />}
    </div>
  );
}
