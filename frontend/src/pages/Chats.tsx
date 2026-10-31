import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api, type Bot, type Conversation, type ConversationSummary, type Message } from "../api";
import { AnswerText } from "../components/AnswerText";
import { BotAvatar } from "../components/BotAvatar";
import { Icon } from "../components/Icon";
import { SourceSlip } from "../components/SourceSlip";
import { formatRelative, plural } from "../format";

interface Tab {
  key: string;
  botId: string;
  conversationId: string | null;
  title: string;
}

type Mode = "tabs" | "split";

interface Saved {
  tabs: Tab[];
  active: string | null;
  mode: Mode;
}

const STORAGE_KEY = "nexo.chats";
const MAX_SPLIT = 3;

function newKey(): string {
  return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

function loadSaved(): Saved {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw) as Saved;
      if (Array.isArray(data.tabs)) {
        return { tabs: data.tabs.slice(0, 12), active: data.active ?? null, mode: data.mode === "split" ? "split" : "tabs" };
      }
    }
  } catch {
    return { tabs: [], active: null, mode: "tabs" };
  }
  return { tabs: [], active: null, mode: "tabs" };
}

function persist(value: Saved): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    return;
  }
}

interface PaneProps {
  tab: Tab;
  bot: Bot | undefined;
  focused: boolean;
  compact: boolean;
  onFocus: () => void;
  onClose: () => void;
  onUpdate: (patch: Partial<Tab>) => void;
  onActivity: () => void;
}

function ChatPane({ tab, bot, focused, compact, onFocus, onClose, onUpdate, onActivity }: PaneProps) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<Record<string, number | null>>({});
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!tab.conversationId) {
      setConversation(null);
      return;
    }
    if (conversation?.id === tab.conversationId) return;
    setLoading(true);
    api.conversation(tab.conversationId)
      .then((c) => { setConversation(c); onUpdate({ title: c.title }); })
      .catch((e: ApiError) => { setError(e.message); onUpdate({ conversationId: null, title: "Nova conversa" }); })
      .finally(() => setLoading(false));
  }, [tab.conversationId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation?.items.length, pending]);

  useEffect(() => {
    if (focused) textarea.current?.focus();
  }, [focused]);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const text = question.trim();
    if (!text || pending || !bot) return;
    setError("");
    setPending(text);
    setQuestion("");
    try {
      let current = conversation;
      if (!current) {
        current = await api.createBotConversation(bot.id);
        setConversation(current);
        onUpdate({ conversationId: current.id });
      }
      const exchange = await api.ask(current.id, text);
      const next = { ...current, ...exchange.conversation, items: [...current.items, exchange.question, exchange.answer] };
      setConversation(next);
      onUpdate({ conversationId: next.id, title: next.title });
      onActivity();
    } catch (err) {
      setError((err as ApiError).message);
      setQuestion(text);
    } finally {
      setPending(null);
      textarea.current?.focus();
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit();
    }
  }

  function toggle(message: Message, rank: number | null) {
    setOpen((current) => {
      const has = message.id in current;
      if (has && (rank === null || current[message.id] === rank)) {
        const next = { ...current };
        delete next[message.id];
        return next;
      }
      return { ...current, [message.id]: rank };
    });
  }

  const items = conversation?.items ?? [];

  return (
    <section className={`pane${focused ? " pane--focused" : ""}${compact ? " pane--compact" : ""}`}
      aria-label={`Chat com ${bot?.name ?? "agente"}`} onMouseDown={onFocus}>
      <header className="pane__head">
        {bot ? <BotAvatar name={bot.name} color={bot.color} size={36} /> : <span className="bot-avatar bot-avatar--gone" />}
        <div className="pane__who">
          <strong>{bot?.name ?? "Agente excluído"}</strong>
          <span>
            {bot ? <>Base: <Link to={`/bases/${bot.base_id}`}>{bot.base_name}</Link></> : "Este agente não existe mais."}
            {conversation && conversation.title !== "Nova conversa" ? <> · {conversation.title}</> : null}
          </span>
        </div>
        <button className="icon-button" onClick={(e) => { e.stopPropagation(); onClose(); }} aria-label="Fechar chat" title="Fechar chat">
          <Icon name="close" size={16} />
        </button>
      </header>

      <div className="pane__messages">
        {loading && <p className="pane__loading">Carregando a conversa…</p>}
        {!loading && bot && items.length === 0 && !pending && (
          <>
            <div className="msg msg--bot pane__greeting">
              <div className="greeting-bubble">
                <p>{bot.greeting || `Olá! Eu sou ${bot.name}. Pergunte sobre o que está na base ${bot.base_name}.`}</p>
              </div>
            </div>
            {!bot.ready && (
              <p className="alert" role="status">
                <span className="pane__notice">A base {bot.base_name} ainda não tem conteúdo pronto. <Link to={`/bases/${bot.base_id}`}>Adicione arquivos ou textos</Link>.</span>
              </p>
            )}
          </>
        )}
        {items.map((m, index) => {
          if (m.role === "user") return <div key={m.id} className="msg msg--user"><p>{m.content}</p></div>;
          const shown = m.id in open;
          const query = items[index - 1]?.content ?? "";
          return (
            <div key={m.id} className={`msg msg--bot${m.answered === false ? " msg--missing" : ""}`}>
              {m.answered === false ? (
                <div className="missing"><strong>{m.content}</strong></div>
              ) : (
                <AnswerText text={m.content} sources={m.sources.length} active={shown ? open[m.id] : null}
                  onCite={(rank) => toggle(m, rank)} />
              )}
              <footer className="msg__foot">
                {m.sources.length > 0 && (
                  <button className="link-button" onClick={() => toggle(m, null)} aria-expanded={shown}>
                    {shown ? "Ocultar trechos" : `Ver ${plural(m.sources.length, "trecho", "trechos")}`}
                  </button>
                )}
                {m.latency_ms !== null && (
                  <span className="msg__model">{(m.latency_ms / 1000).toFixed(1).replace(".", ",")} s</span>
                )}
              </footer>
              {shown && (
                <ol className="pane__sources">
                  {m.sources
                    .filter((s) => open[m.id] === null || open[m.id] === undefined || s.rank === open[m.id])
                    .map((s) => (
                      <li key={s.rank}>
                        <SourceSlip source={s} query={query} active={open[m.id] === s.rank} onError={setError} />
                      </li>
                    ))}
                </ol>
              )}
            </div>
          );
        })}
        {pending && (
          <>
            <div className="msg msg--user"><p>{pending}</p></div>
            <div className="msg msg--bot msg--pending" role="status">
              <div className="busline" aria-hidden="true"><span /></div>
              <p>{bot?.name ?? "O agente"} está consultando a base…</p>
            </div>
          </>
        )}
        <div ref={bottom} />
      </div>

      {error && <p className="alert pane__error" role="alert">{error}</p>}

      <form className="composer pane__composer" onSubmit={submit}>
        <textarea ref={textarea} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey}
          placeholder={bot ? `Pergunte a ${bot.name}` : "Agente indisponível"} aria-label={`Mensagem para ${bot?.name ?? "o agente"}`}
          rows={1} maxLength={4000} disabled={!!pending || !bot} />
        <button className="send" type="submit" disabled={!question.trim() || !!pending || !bot} aria-label="Enviar mensagem">
          <Icon name="send" />
        </button>
      </form>
    </section>
  );
}

export function ChatsPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [saved, setSaved] = useState<Saved>(loadSaved);
  const [picker, setPicker] = useState(false);
  const [filter, setFilter] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const { tabs, active, mode } = saved;

  const loadConversations = useCallback(() => {
    api.botConversations().then(setConversations).catch(() => undefined);
  }, []);

  useEffect(() => {
    api.bots().then(setBots).catch(() => setBots([]));
    loadConversations();
  }, [loadConversations]);

  useEffect(() => persist(saved), [saved]);

  const update = (fn: (s: Saved) => Saved) => setSaved((s) => fn(s));

  const openBot = useCallback((botId: string) => {
    const key = newKey();
    update((s) => ({ ...s, tabs: [...s.tabs, { key, botId, conversationId: null, title: "Nova conversa" }].slice(-12), active: key }));
    setPicker(false);
    setListOpen(false);
  }, []);

  const openConversation = (c: ConversationSummary) => {
    if (!c.bot_id) return;
    const existing = tabs.find((t) => t.conversationId === c.id);
    if (existing) {
      update((s) => ({ ...s, active: existing.key }));
    } else {
      const key = newKey();
      update((s) => ({ ...s, tabs: [...s.tabs, { key, botId: c.bot_id!, conversationId: c.id, title: c.title }].slice(-12), active: key }));
    }
    setListOpen(false);
  };

  const handled = useRef<string | null>(null);
  useEffect(() => {
    const agent = params.get("agente");
    if (!agent) {
      handled.current = null;
      return;
    }
    if (handled.current === params.toString()) return;
    handled.current = params.toString();
    openBot(agent);
    navigate("/chats", { replace: true });
  }, [params, openBot, navigate]);

  function close(key: string) {
    update((s) => {
      const index = s.tabs.findIndex((t) => t.key === key);
      const rest = s.tabs.filter((t) => t.key !== key);
      const nextActive = s.active === key ? (rest[Math.min(index, rest.length - 1)]?.key ?? null) : s.active;
      return { ...s, tabs: rest, active: nextActive };
    });
  }

  function patch(key: string, value: Partial<Tab>) {
    update((s) => ({ ...s, tabs: s.tabs.map((t) => (t.key === key ? { ...t, ...value } : t)) }));
  }

  const byId = useMemo(() => new Map((bots ?? []).map((b) => [b.id, b])), [bots]);
  const activeTab = tabs.find((t) => t.key === active) ?? tabs[tabs.length - 1];
  const activeIndex = activeTab ? tabs.indexOf(activeTab) : 0;
  const visible = mode === "split"
    ? tabs.slice(Math.max(0, Math.min(activeIndex, tabs.length - MAX_SPLIT)), Math.max(0, Math.min(activeIndex, tabs.length - MAX_SPLIT)) + MAX_SPLIT)
    : activeTab ? [activeTab] : [];

  const q = filter.trim().toLowerCase();
  const shownBots = (bots ?? []).filter((b) => !q || b.name.toLowerCase().includes(q) || b.base_name.toLowerCase().includes(q));

  if (bots && bots.length === 0) {
    return (
      <div className="page">
        <header className="page__head">
          <div className="page__titles">
            <span className="page__over">Agentes</span>
            <h1>Chats com agentes</h1>
            <p className="page__lead">Converse com vários agentes ao mesmo tempo, em abas ou lado a lado.</p>
          </div>
        </header>
        <div className="box"><section className="panel agents-empty">
          <span className="agents-empty__icon"><Icon name="chats" size={26} /></span>
          <h2 className="fina">Nenhum agente para conversar</h2>
          <p className="panel__lead">Crie um agente, escolha a base de conhecimento dele e volte aqui para abrir quantos chats quiser.</p>
          <Link className="primary-button" to="/agentes"><Icon name="plus" size={16} />Criar agente</Link>
        </section></div>
      </div>
    );
  }

  return (
    <div className={`chats${listOpen ? " chats--list" : ""}`}>
      <aside className="chats__side" aria-label="Agentes e conversas">
        <div className="chats__side-head">
          <h2>Agentes</h2>
          <Link className="icon-button" to="/agentes" title="Gerenciar agentes" aria-label="Gerenciar agentes"><Icon name="edit" size={16} /></Link>
        </div>
        <input className="threads__filter" value={filter} onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar agentes" aria-label="Filtrar agentes" />
        <ul className="chats__bots">
          {shownBots.map((b) => {
            const recent = conversations.filter((c) => c.bot_id === b.id).slice(0, 3);
            return (
              <li key={b.id}>
                <button className="chats__bot" onClick={() => openBot(b.id)} title={`Novo chat com ${b.name}`}>
                  <BotAvatar name={b.name} color={b.color} size={30} />
                  <span>
                    <strong>{b.name}</strong>
                    <small>{b.base_name}</small>
                  </span>
                  <Icon name="plus" size={15} />
                </button>
                {recent.length > 0 && (
                  <ul className="chats__recent">
                    {recent.map((c) => (
                      <li key={c.id}>
                        <button className={tabs.some((t) => t.conversationId === c.id) ? "is-open" : ""} onClick={() => openConversation(c)}>
                          <span>{c.title}</span>
                          <small>{formatRelative(c.updated_at)}</small>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </aside>

      <section className="chats__main">
        <div className="chats__bar">
          <button className="ghost-button small chats__toggle-list" onClick={() => setListOpen(!listOpen)}>
            {listOpen ? "Fechar" : "Agentes"}
          </button>
          <div className="chat-tabs" role="tablist" aria-label="Chats abertos">
            {tabs.map((t) => {
              const b = byId.get(t.botId);
              const on = activeTab?.key === t.key;
              const inSplit = mode === "split" && visible.some((v) => v.key === t.key);
              return (
                <div key={t.key} className={`chat-tab${on ? " chat-tab--on" : ""}${inSplit && !on ? " chat-tab--shown" : ""}`}>
                  <button role="tab" aria-selected={on} className="chat-tab__open" onClick={() => update((s) => ({ ...s, active: t.key }))}>
                    {b ? <BotAvatar name={b.name} color={b.color} size={20} /> : <span className="bot-avatar bot-avatar--gone" style={{ width: 20, height: 20 }} />}
                    <span className="chat-tab__text">
                      <strong>{b?.name ?? "Agente"}</strong>
                      <small>{t.title}</small>
                    </span>
                  </button>
                  <button className="chat-tab__close" onClick={() => close(t.key)} aria-label={`Fechar chat com ${b?.name ?? "agente"}`}>
                    <Icon name="close" size={13} />
                  </button>
                </div>
              );
            })}
            <span className="menu-anchor">
              <button className="icon-button chat-tabs__add" onClick={() => setPicker(!picker)} aria-label="Abrir novo chat" title="Novo chat" aria-expanded={picker}>
                <Icon name="plus" size={16} />
              </button>
              {picker && (
                <span className="menu chat-picker" role="menu">
                  {(bots ?? []).map((b) => (
                    <button key={b.id} role="menuitem" onClick={() => openBot(b.id)}>
                      <span className="chat-picker__row"><BotAvatar name={b.name} color={b.color} size={22} />{b.name}</span>
                      <small>{b.base_name}</small>
                    </button>
                  ))}
                </span>
              )}
            </span>
          </div>
          <div className="segmented chats__mode" role="tablist" aria-label="Modo de exibição">
            <button role="tab" aria-selected={mode === "tabs"} onClick={() => update((s) => ({ ...s, mode: "tabs" }))}>
              <Icon name="tabs" size={15} />Abas
            </button>
            <button role="tab" aria-selected={mode === "split"} onClick={() => update((s) => ({ ...s, mode: "split" }))}>
              <Icon name="split" size={15} />Lado a lado
            </button>
          </div>
        </div>

        {bots === null ? (
          <p className="chats__loading">Carregando os agentes…</p>
        ) : tabs.length === 0 ? (
          <div className="chats__empty">
            <h2 className="fina">Abra um chat</h2>
            <p>Escolha um agente na lista ou no botão +. Você pode abrir vários chats, alternar entre as abas ou ver até três lado a lado.</p>
            <div className="chats__starters">
              {(bots ?? []).slice(0, 6).map((b) => (
                <button key={b.id} className="starter" onClick={() => openBot(b.id)}>
                  <BotAvatar name={b.name} color={b.color} size={36} />
                  <span><strong>{b.name}</strong><small>{b.description || b.base_name}</small></span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className={`panes panes--${Math.max(1, visible.length)}${mode === "split" ? " panes--split" : ""}`}>
            {visible.map((t) => (
              <ChatPane key={t.key} tab={t} bot={byId.get(t.botId)} focused={activeTab?.key === t.key}
                compact={mode === "split" && visible.length > 1}
                onFocus={() => { if (active !== t.key) update((s) => ({ ...s, active: t.key })); }}
                onClose={() => close(t.key)} onUpdate={(p) => patch(t.key, p)} onActivity={loadConversations} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
