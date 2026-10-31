import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api, type Bot, type BotInput, type KnowledgeBase } from "../api";
import { BOT_COLORS, BotAvatar } from "../components/BotAvatar";
import { Icon } from "../components/Icon";
import { useToast } from "../components/Toast";
import { plural } from "../format";

const NEW_BASE = "__nova__";

interface Draft {
  name: string;
  description: string;
  base_id: string;
  instructions: string;
  greeting: string;
  fallback: string;
  color: string;
  cite_sources: boolean;
}

function emptyDraft(bases: KnowledgeBase[]): Draft {
  const base = bases.find((b) => b.is_default) ?? bases[0];
  return {
    name: "",
    description: "",
    base_id: base?.id ?? "",
    instructions: "",
    greeting: "",
    fallback: "",
    color: BOT_COLORS[0],
    cite_sources: true,
  };
}

function fromBot(bot: Bot): Draft {
  return {
    name: bot.name,
    description: bot.description ?? "",
    base_id: bot.base_id,
    instructions: bot.instructions ?? "",
    greeting: bot.greeting ?? "",
    fallback: bot.fallback ?? "",
    color: bot.color,
    cite_sources: bot.cite_sources,
  };
}

function Drawer({ bot, bases, onClose, onSaved, onBaseCreated }: {
  bot: Bot | null;
  bases: KnowledgeBase[];
  onClose: () => void;
  onSaved: (bot: Bot) => void;
  onBaseCreated: (base: KnowledgeBase) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => (bot ? fromBot(bot) : emptyDraft(bases)));
  const [newBase, setNewBase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setFields({});
    setBusy(true);
    try {
      let baseId = draft.base_id;
      if (baseId === NEW_BASE) {
        if (!newBase.trim()) {
          setFields({ base_id: "Dê um nome para a nova base." });
          setBusy(false);
          return;
        }
        const created = await api.createBase({ name: newBase.trim() });
        onBaseCreated(created);
        baseId = created.id;
        set("base_id", created.id);
      }
      const input: BotInput = {
        name: draft.name.trim(),
        base_id: baseId,
        description: draft.description.trim() || null,
        instructions: draft.instructions.trim() || null,
        greeting: draft.greeting.trim() || null,
        fallback: draft.fallback.trim() || null,
        color: draft.color,
        cite_sources: draft.cite_sources,
      };
      const saved = bot ? await api.updateBot(bot.id, input) : await api.createBot(input);
      onSaved(saved);
    } catch (err) {
      const apiError = err as ApiError;
      setFields(apiError.fields ?? {});
      setError(apiError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={bot ? "Editar agente" : "Novo agente"}
        onMouseDown={(e) => e.stopPropagation()}>
        <header className="drawer__head">
          <div className="drawer__who">
            <BotAvatar name={draft.name || "Agente"} color={draft.color} size={44} />
            <div>
              <span className="page__over">{bot ? "Editar agente" : "Novo agente"}</span>
              <h2 className="fina drawer__title">{draft.name.trim() || "Sem nome"}</h2>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fechar"><Icon name="close" /></button>
        </header>
        <form className="drawer__form" onSubmit={submit} noValidate>
          <div className={`field${fields.name ? " field--error" : ""}`}>
            <label htmlFor="bot-nome">Nome</label>
            <input id="bot-nome" value={draft.name} maxLength={80} autoFocus required
              placeholder="Ex.: Suporte técnico" onChange={(e) => set("name", e.target.value)} />
            {fields.name && <p className="field__message">{fields.name}</p>}
          </div>
          <div className="field">
            <label htmlFor="bot-descricao">Descrição</label>
            <input id="bot-descricao" value={draft.description} maxLength={300}
              placeholder="Para que serve este agente" onChange={(e) => set("description", e.target.value)} />
          </div>
          <div className={`field${fields.base_id ? " field--error" : ""}`}>
            <label htmlFor="bot-base">Base de conhecimento</label>
            <select id="bot-base" value={draft.base_id} onChange={(e) => set("base_id", e.target.value)}>
              {bases.map((b) => (
                <option key={b.id} value={b.id}>{b.name} ({plural(b.ready, "item pronto", "itens prontos")})</option>
              ))}
              <option value={NEW_BASE}>+ Criar nova base</option>
            </select>
            {draft.base_id === NEW_BASE && (
              <input className="drawer__newbase" value={newBase} maxLength={120} placeholder="Nome da nova base"
                aria-label="Nome da nova base" onChange={(e) => setNewBase(e.target.value)} />
            )}
            {fields.base_id ? <p className="field__message">{fields.base_id}</p>
              : <p className="field__hint">O agente só responde com o que estiver nessa base.</p>}
          </div>
          <div className="field">
            <label htmlFor="bot-instrucoes">Instruções</label>
            <textarea id="bot-instrucoes" value={draft.instructions} rows={5} maxLength={4000}
              placeholder="Tom, persona e regras. Ex.: Fale de forma cordial e objetiva, trate o cliente por você, ofereça o passo a passo."
              onChange={(e) => set("instructions", e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="bot-saudacao">Saudação</label>
            <input id="bot-saudacao" value={draft.greeting} maxLength={500}
              placeholder="Ex.: Olá! Sou o assistente de suporte. Como posso ajudar?" onChange={(e) => set("greeting", e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="bot-fallback">Resposta quando não souber</label>
            <input id="bot-fallback" value={draft.fallback} maxLength={500}
              placeholder="Ex.: Não encontrei isso nos meus documentos. Vou chamar uma pessoa da equipe."
              onChange={(e) => set("fallback", e.target.value)} />
          </div>
          <fieldset className="swatches">
            <legend>Cor</legend>
            {BOT_COLORS.map((c) => (
              <button key={c} type="button" className={`swatch${draft.color === c ? " swatch--on" : ""}`}
                style={{ background: c }} aria-label={`Cor ${c}`} aria-pressed={draft.color === c}
                onClick={() => set("color", c)} />
            ))}
          </fieldset>
          <label className="check">
            <input type="checkbox" checked={draft.cite_sources} onChange={(e) => set("cite_sources", e.target.checked)} />
            Citar as fontes nas respostas
          </label>
          {error && <p className="alert" role="alert">{error}</p>}
          <div className="drawer__actions">
            <button className="primary-button" type="submit" disabled={busy || !draft.name.trim()}>
              {busy ? "Salvando…" : bot ? "Salvar agente" : "Criar agente"}
            </button>
            <button className="ghost-button" type="button" onClick={onClose}>Cancelar</button>
          </div>
        </form>
      </aside>
    </div>
  );
}

export function AgentsPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [editing, setEditing] = useState<Bot | null | "new">(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = () => {
    api.bots().then(setBots).catch((e: ApiError) => { setBots([]); setError(e.message); });
    api.bases().then(setBases).catch(() => undefined);
  };
  useEffect(load, []);

  const stats = useMemo(() => {
    const list = bots ?? [];
    return {
      conversations: list.reduce((sum, b) => sum + b.conversations, 0),
      bases: new Set(list.map((b) => b.base_id)).size,
      ready: list.filter((b) => b.ready).length,
    };
  }, [bots]);

  async function remove(bot: Bot) {
    try {
      await api.deleteBot(bot.id);
      setConfirm(null);
      toast(`Agente ${bot.name} excluído.`);
      load();
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  function saved(bot: Bot) {
    const isNew = editing === "new";
    setEditing(null);
    toast(isNew ? `Agente ${bot.name} criado.` : "Agente salvo.");
    load();
  }

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Agentes</span>
          <h1>Agentes</h1>
          <p className="page__lead">Cada agente tem nome, instruções e uma base de conhecimento. Ele responde só com o que está nessa base.</p>
        </div>
        <button className="primary-button" onClick={() => setEditing("new")} disabled={!bases.length}>
          <Icon name="plus" size={16} />Novo agente
        </button>
      </header>

      {error && <p className="alert" role="alert">{error}</p>}

      <div className="box box--agents">
        <section className="lid agents-lid" aria-label="Resumo dos agentes">
          <span className="lid__label">Agentes criados</span>
          <strong className="lid__number">{bots === null ? "—" : bots.length}</strong>
          <p className="lid__sub">
            {bots === null ? "Carregando…" : bots.length === 0 ? "Nenhum agente ainda."
              : `${plural(stats.ready, "agente pronto", "agentes prontos")} para conversar.`}
          </p>
          <dl className="lid__stats agents-lid__stats">
            <div><dt>Agentes</dt><dd>{bots?.length ?? 0}</dd></div>
            <div><dt>Conversas</dt><dd>{stats.conversations.toLocaleString("pt-BR")}</dd></div>
            <div><dt>Bases usadas</dt><dd>{stats.bases}</dd></div>
          </dl>
        </section>
        <section className="agents-how">
          <h2>Como funciona</h2>
          <ol className="steps">
            <li><span>1</span><div><strong>Monte a base</strong><p>Envie PDFs, Word, planilhas CSV ou digite textos em <Link to="/bases">Bases de conhecimento</Link>.</p></div></li>
            <li><span>2</span><div><strong>Crie o agente</strong><p>Dê um nome, escreva as instruções e escolha a base.</p></div></li>
            <li><span>3</span><div><strong>Converse</strong><p>Abra vários chats em <Link to="/chats">Chats com agentes</Link> ou ligue o agente ao <Link to="/whatsapp">WhatsApp</Link>.</p></div></li>
          </ol>
        </section>
      </div>

      {bots && bots.length === 0 && (
        <div className="box"><section className="panel agents-empty">
          <span className="agents-empty__icon"><Icon name="bot" size={26} /></span>
          <h2 className="fina">Crie seu primeiro agente</h2>
          <p className="panel__lead">Um agente de suporte, um de vendas, outro para a equipe interna: cada um com a própria base e o próprio jeito de falar.</p>
          <button className="primary-button" onClick={() => setEditing("new")} disabled={!bases.length}>
            <Icon name="plus" size={16} />Novo agente
          </button>
        </section></div>
      )}

      {bots && bots.length > 0 && (
        <ul className="agent-grid">
          {bots.map((bot) => (
            <li key={bot.id} className="agent-card">
              <div className="agent-card__top">
                <BotAvatar name={bot.name} color={bot.color} size={48} />
                <div className="agent-card__titles">
                  <h2>{bot.name}</h2>
                  <span className={`dot-status${bot.ready ? " dot-status--ok" : " dot-status--warn"}`}>
                    {bot.ready ? "Pronto para conversar" : "Base sem conteúdo pronto"}
                  </span>
                </div>
              </div>
              <p className="agent-card__desc">{bot.description || "Sem descrição."}</p>
              <dl className="agent-card__meta">
                <div><dt>Base</dt><dd><Link to={`/bases/${bot.base_id}`}><Icon name="base" size={14} />{bot.base_name}</Link></dd></div>
                <div><dt>Conversas</dt><dd>{bot.conversations.toLocaleString("pt-BR")}</dd></div>
                <div><dt>Fontes</dt><dd>{bot.cite_sources ? "Cita" : "Não cita"}</dd></div>
              </dl>
              {confirm === bot.id ? (
                <div className="agent-card__confirm">
                  <span>Excluir o agente e {plural(bot.conversations, "conversa", "conversas")} com ele?</span>
                  <div>
                    <button className="danger-button small" onClick={() => remove(bot)}>Excluir</button>
                    <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                  </div>
                </div>
              ) : (
                <div className="agent-card__actions">
                  <button className="primary-button small" onClick={() => navigate(`/chats?agente=${bot.id}`)}>
                    <Icon name="chat" size={15} />Conversar
                  </button>
                  {bot.can_edit && (
                    <>
                      <button className="icon-button" title="Editar" aria-label={`Editar ${bot.name}`} onClick={() => setEditing(bot)}>
                        <Icon name="edit" size={16} />
                      </button>
                      <button className="icon-button" title="Excluir" aria-label={`Excluir ${bot.name}`} onClick={() => setConfirm(bot.id)}>
                        <Icon name="trash" size={16} />
                      </button>
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {editing !== null && (
        <Drawer bot={editing === "new" ? null : editing} bases={bases} onClose={() => setEditing(null)} onSaved={saved}
          onBaseCreated={(b) => setBases((list) => [...list, b])} />
      )}
    </div>
  );
}
