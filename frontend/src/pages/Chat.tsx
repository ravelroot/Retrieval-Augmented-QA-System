import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, type Conversation, type ConversationSummary, type DocumentItem, type Message } from "../api";
import { AnswerText } from "../components/AnswerText";
import { Icon } from "../components/Icon";
import { SourcesPanel } from "../components/SourcesPanel";
import { formatRelative, plural } from "../format";

interface Selection {
  messageId: string;
  rank: number | null;
}

export function ChatPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [list, setList] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [draftScope, setDraftScope] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const loadList = useCallback(() => {
    api.conversations().then(setList).catch((e: ApiError) => setError(e.message));
  }, []);

  useEffect(() => {
    loadList();
    api.documents().then(setDocs).catch((e: ApiError) => setError(e.message));
  }, [loadList]);

  useEffect(() => {
    setSelection(null);
    setError("");
    setRenaming(false);
    setListOpen(false);
    if (!id) {
      setConversation(null);
      return;
    }
    if (conversation?.id === id) return;
    api.conversation(id).then(setConversation).catch((e: ApiError) => {
      setError(e.message);
      navigate("/conversas", { replace: true });
    });
  }, [id]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation?.items.length, pending]);

  const ready = useMemo(() => docs.filter((d) => d.status === "READY"), [docs]);
  const scope = conversation ? conversation.document_ids : draftScope;
  const scoped = ready.filter((d) => scope.includes(d.id));

  const selectedMessage = conversation?.items.find((m) => m.id === selection?.messageId) ?? null;

  async function setScope(next: string[]) {
    if (!conversation) {
      setDraftScope(next);
      return;
    }
    try {
      const summary = await api.updateConversation(conversation.id, { document_ids: next });
      setConversation({ ...conversation, ...summary });
      loadList();
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const text = question.trim();
    if (!text || pending) return;
    setError("");
    setPending(text);
    setQuestion("");
    try {
      let current = conversation;
      if (!current) {
        current = await api.createConversation(draftScope);
        setConversation(current);
        navigate(`/conversas/${current.id}`, { replace: true });
      }
      const exchange = await api.ask(current.id, text);
      setConversation({ ...current, ...exchange.conversation, items: [...current.items, exchange.question, exchange.answer] });
      if (exchange.answer.sources.length) setSelection({ messageId: exchange.answer.id, rank: null });
      loadList();
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

  async function rate(message: Message, rating: number) {
    if (!conversation) return;
    try {
      const updated = await api.feedback(message.id, message.my_rating === rating ? 0 : rating);
      setConversation({ ...conversation, items: conversation.items.map((m) => (m.id === updated.id ? updated : m)) });
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  async function remove(target: string) {
    try {
      await api.deleteConversation(target);
      setConfirmDelete(null);
      loadList();
      if (target === conversation?.id) navigate("/conversas");
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  async function saveTitle(e: FormEvent) {
    e.preventDefault();
    if (!conversation || !title.trim()) return setRenaming(false);
    try {
      const summary = await api.updateConversation(conversation.id, { title: title.trim() });
      setConversation({ ...conversation, ...summary });
      loadList();
    } catch (err) {
      setError((err as ApiError).message);
    }
    setRenaming(false);
  }

  const items = conversation?.items ?? [];

  return (
    <div className={`chat${selectedMessage ? " chat--sources" : ""}${listOpen ? " chat--list" : ""}`}>
      <section className="threads" aria-label="Conversas">
        <div className="threads__head">
          <h2>Conversas</h2>
          <Link className="primary-button small" to="/conversas" onClick={() => setDraftScope([])}>
            <Icon name="plus" size={16} />
            Nova
          </Link>
        </div>
        {list.length === 0 ? (
          <p className="threads__empty">As conversas que você abrir aparecem aqui.</p>
        ) : (
          <ul>
            {list.map((c) => (
              <li key={c.id} className={c.id === id ? "thread thread--active" : "thread"}>
                {confirmDelete === c.id ? (
                  <div className="thread__confirm">
                    <span>Apagar esta conversa?</span>
                    <button className="danger-button small" onClick={() => remove(c.id)}>Apagar</button>
                    <button className="ghost-button small" onClick={() => setConfirmDelete(null)}>Manter</button>
                  </div>
                ) : (
                  <>
                    <Link to={`/conversas/${c.id}`} className="thread__link">
                      <span className="thread__title">{c.title}</span>
                      <span className="thread__meta">
                        {formatRelative(c.updated_at)}, {c.document_ids.length ? plural(c.document_ids.length, "documento", "documentos") : "todos os documentos"}
                      </span>
                    </Link>
                    <button className="icon-button thread__delete" aria-label={`Apagar ${c.title}`} onClick={() => setConfirmDelete(c.id)}>
                      <Icon name="trash" size={16} />
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="dialog" aria-label="Conversa">
        <header className="dialog__head">
          <button className="ghost-button small dialog__threads" onClick={() => setListOpen(!listOpen)}>
            {listOpen ? "Fechar lista" : "Conversas"}
          </button>
          {renaming && conversation ? (
            <form className="inline-form" onSubmit={saveTitle}>
              <input aria-label="Título da conversa" value={title} autoFocus maxLength={160}
                onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setRenaming(false)} />
              <button className="primary-button small" type="submit">Salvar</button>
            </form>
          ) : (
            <h1 className="dialog__title">
              {conversation?.title ?? "Nova conversa"}
              {conversation && (
                <button className="icon-button" aria-label="Renomear conversa" onClick={() => { setTitle(conversation.title); setRenaming(true); }}>
                  <Icon name="edit" size={16} />
                </button>
              )}
            </h1>
          )}
        </header>

        <div className="scope">
          <div className="scope__line" aria-hidden="true" />
          <div className="scope__nodes">
            <span className="scope__label">Consultando</span>
            {scoped.length === 0 ? (
              <span className="scope__node">Todos os documentos prontos ({ready.length})</span>
            ) : (
              scoped.map((d) => <span key={d.id} className="scope__node">{d.title}</span>)
            )}
            <button className="scope__edit" onClick={() => setScopeOpen(!scopeOpen)} aria-expanded={scopeOpen}>
              {scopeOpen ? "Concluir" : "Escolher documentos"}
            </button>
          </div>
          {scopeOpen && (
            <div className="scope__picker">
              {ready.length === 0 ? (
                <p>Nenhum documento pronto. <Link to="/documentos">Envie PDFs</Link> para começar.</p>
              ) : (
                <>
                  <label className="check">
                    <input type="checkbox" checked={scope.length === 0} onChange={() => setScope([])} />
                    Todos os documentos prontos
                  </label>
                  {ready.map((d) => (
                    <label key={d.id} className="check">
                      <input type="checkbox" checked={scope.includes(d.id)}
                        onChange={(e) => setScope(e.target.checked ? [...scope, d.id] : scope.filter((x) => x !== d.id))} />
                      {d.title}
                      <small>{plural(d.pages, "página", "páginas")}</small>
                    </label>
                  ))}
                </>
              )}
            </div>
          )}
        </div>

        <div className="messages">
          {items.length === 0 && !pending && (
            <div className="empty">
              {ready.length === 0 ? (
                <>
                  <h2>Envie um PDF para começar</h2>
                  <p>O Nexo só responde com o que estiver nos documentos indexados.</p>
                  <Link className="primary-button" to="/documentos">Ir para Documentos</Link>
                </>
              ) : (
                <>
                  <h2>O que você quer saber?</h2>
                  <p>Pergunte sobre {scoped.length ? plural(scoped.length, "o documento escolhido", "os documentos escolhidos") : plural(ready.length, "o documento pronto", "os documentos prontos")}. Cada resposta indica o trecho e a página de origem.</p>
                </>
              )}
            </div>
          )}
          {items.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="msg msg--user"><p>{m.content}</p></div>
            ) : (
              <div key={m.id} className={`msg msg--bot${m.answered === false ? " msg--missing" : ""}`}>
                {m.answered === false ? (
                  <div className="missing">
                    <strong>{m.content}</strong>
                    <p>Tente outras palavras, amplie os documentos consultados ou envie o PDF que trata do assunto.</p>
                  </div>
                ) : (
                  <AnswerText text={m.content} sources={m.sources.length}
                    active={selection?.messageId === m.id ? selection.rank : null}
                    onCite={(rank) => setSelection({ messageId: m.id, rank })} />
                )}
                <footer className="msg__foot">
                  {m.sources.length > 0 && (
                    <button className="link-button" onClick={() => setSelection({ messageId: m.id, rank: null })}>
                      Ver {plural(m.sources.length, "trecho", "trechos")}
                    </button>
                  )}
                  {m.grounded === false && <span className="warn">A verificação automática não confirmou todos os pontos.</span>}
                  <span className="msg__model">{m.model}{m.latency_ms !== null ? `, ${(m.latency_ms / 1000).toFixed(1).replace(".", ",")} s` : ""}</span>
                  <span className="rate">
                    <button className={`icon-button${m.my_rating === 1 ? " is-on" : ""}`} aria-pressed={m.my_rating === 1}
                      aria-label="Resposta útil" onClick={() => rate(m, 1)}>
                      <Icon name="up" size={16} />
                    </button>
                    <button className={`icon-button${m.my_rating === -1 ? " is-on" : ""}`} aria-pressed={m.my_rating === -1}
                      aria-label="Resposta não ajudou" onClick={() => rate(m, -1)}>
                      <Icon name="down" size={16} />
                    </button>
                  </span>
                </footer>
              </div>
            ),
          )}
          {pending && (
            <>
              <div className="msg msg--user"><p>{pending}</p></div>
              <div className="msg msg--bot msg--pending" role="status">
                <div className="busline" aria-hidden="true"><span /></div>
                <p>Buscando nos documentos e conferindo os trechos…</p>
              </div>
            </>
          )}
          <div ref={bottom} />
        </div>

        {error && <p className="alert chat__error" role="alert">{error}</p>}

        <form className="composer" onSubmit={submit}>
          <textarea ref={textarea} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey}
            placeholder={ready.length ? "Pergunte algo sobre os documentos" : "Envie um PDF em Documentos para perguntar"}
            aria-label="Pergunta" rows={2} maxLength={4000} disabled={!!pending} />
          <button className="send" type="submit" disabled={!question.trim() || !!pending || ready.length === 0} aria-label="Enviar pergunta">
            <Icon name="send" />
          </button>
        </form>
        <p className="composer__hint">Enter envia, Shift + Enter quebra a linha.</p>
      </section>

      {selectedMessage && (
        <SourcesPanel sources={selectedMessage.sources} active={selection?.rank ?? null}
          onSelect={(rank) => setSelection({ messageId: selectedMessage.id, rank })}
          onClose={() => setSelection(null)} onError={setError} />
      )}
    </div>
  );
}
