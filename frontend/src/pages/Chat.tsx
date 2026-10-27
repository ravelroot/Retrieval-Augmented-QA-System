import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api, downloadExport, type Conversation, type Message } from "../api";
import { AnswerText } from "../components/AnswerText";
import { Icon } from "../components/Icon";
import { SourcesPanel } from "../components/SourcesPanel";
import { useToast } from "../components/Toast";
import { formatDateTime, plural } from "../format";
import { useStore } from "../store";

interface Selection {
  messageId: string;
  rank: number | null;
}

function plainAnswer(m: Message): string {
  const refs = m.sources.map((s) => `[${s.rank}] ${s.document_title}, página ${s.page}`).join("\n");
  return refs ? `${m.content}\n\nFontes:\n${refs}` : m.content;
}

export function ChatPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { documents, reloadConversations, reloadDocuments } = useStore();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [draftScope, setDraftScope] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [scopeFilter, setScopeFilter] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(reloadDocuments, [reloadDocuments]);

  useEffect(() => {
    setSelection(null);
    setError("");
    setRenaming(false);
    setExportOpen(false);
    if (!id) {
      setConversation(null);
      const doc = params.get("documento");
      setDraftScope(doc ? [doc] : []);
      setQuestion(params.get("pergunta") ?? "");
      textarea.current?.focus();
      return;
    }
    if (conversation?.id === id) return;
    api.conversation(id).then(setConversation).catch((e: ApiError) => {
      toast(e.message, "error");
      navigate("/conversas", { replace: true });
    });
  }, [id, params]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation?.items.length, pending]);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [question]);

  const ready = useMemo(() => documents.filter((d) => d.status === "READY"), [documents]);
  const scope = conversation ? conversation.document_ids : draftScope;
  const scoped = ready.filter((d) => scope.includes(d.id));
  const items = conversation?.items ?? [];
  const selectedIndex = items.findIndex((m) => m.id === selection?.messageId);
  const selectedMessage = selectedIndex >= 0 ? items[selectedIndex] : null;
  const selectedQuery = selectedIndex > 0 ? items[selectedIndex - 1].content : "";
  const pickable = ready.filter((d) => d.title.toLowerCase().includes(scopeFilter.trim().toLowerCase()));

  async function setScope(next: string[]) {
    if (!conversation) {
      setDraftScope(next);
      return;
    }
    try {
      const summary = await api.updateConversation(conversation.id, { document_ids: next });
      setConversation({ ...conversation, ...summary });
      reloadConversations();
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  async function submit(e?: FormEvent, override?: string) {
    e?.preventDefault();
    const text = (override ?? question).trim();
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
      reloadConversations();
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
      if (updated.my_rating === -1) toast("Avaliação registrada. Ela aparece no Painel de qualidade.");
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  async function copy(m: Message) {
    try {
      await navigator.clipboard.writeText(plainAnswer(m));
      setCopied(m.id);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      toast("O navegador bloqueou a cópia. Selecione o texto e copie manualmente.", "error");
    }
  }

  async function saveTitle(e: FormEvent) {
    e.preventDefault();
    if (!conversation || !title.trim()) return setRenaming(false);
    try {
      const summary = await api.updateConversation(conversation.id, { title: title.trim() });
      setConversation({ ...conversation, ...summary });
      reloadConversations();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
    setRenaming(false);
  }

  async function exportAs(format: "markdown" | "json") {
    if (!conversation) return;
    setExportOpen(false);
    try {
      await downloadExport(conversation.id, format);
      toast(format === "json" ? "Conversa exportada em JSON." : "Conversa exportada em Markdown.");
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  return (
    <div className={`chat${selectedMessage ? " chat--sources" : ""}`}>
      <section className="reader" aria-label="Conversa">
        <header className="reader__head">
          {renaming && conversation ? (
            <form className="inline-form" onSubmit={saveTitle}>
              <input aria-label="Título da conversa" value={title} autoFocus maxLength={160}
                onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setRenaming(false)} />
              <button className="button button--primary button--small" type="submit">Salvar</button>
            </form>
          ) : (
            <h1 className="reader__title">{conversation?.title ?? "Nova conversa"}</h1>
          )}
          {conversation && !renaming && (
            <div className="reader__tools">
              <button className="icon-button" aria-label="Renomear conversa" title="Renomear"
                onClick={() => { setTitle(conversation.title); setRenaming(true); }}>
                <Icon name="edit" size={17} />
              </button>
              <div className="menu-anchor">
                <button className="icon-button" aria-label="Exportar conversa" title="Exportar" aria-expanded={exportOpen}
                  onClick={() => setExportOpen(!exportOpen)} disabled={!items.length}>
                  <Icon name="download" size={17} />
                </button>
                {exportOpen && (
                  <div className="menu" role="menu">
                    <button role="menuitem" onClick={() => exportAs("markdown")}>Markdown (.md)<small>Para ler ou colar em documentos</small></button>
                    <button role="menuitem" onClick={() => exportAs("json")}>JSON<small>Com trechos e notas, para sistemas</small></button>
                  </div>
                )}
              </div>
            </div>
          )}
        </header>

        <div className="scope">
          <span className="scope__label">Consultando</span>
          <div className="scope__tabs">
            {scoped.length === 0 ? (
              <span className="tab">Todos os documentos prontos <b>{ready.length}</b></span>
            ) : (
              scoped.map((d) => <span key={d.id} className="tab" title={d.title}>{d.title}</span>)
            )}
          </div>
          <button className="text-button" onClick={() => setScopeOpen(!scopeOpen)} aria-expanded={scopeOpen}>
            <Icon name="filter" size={15} />
            {scopeOpen ? "Concluir" : "Escolher documentos"}
          </button>
          {scopeOpen && (
            <div className="scope__picker">
              {ready.length === 0 ? (
                <p>Nenhum documento pronto. <Link to="/documentos">Envie PDFs</Link> para começar.</p>
              ) : (
                <>
                  {ready.length > 6 && (
                    <input className="scope__search" value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}
                      placeholder="Filtrar documentos" aria-label="Filtrar documentos" />
                  )}
                  <label className="check">
                    <input type="checkbox" checked={scope.length === 0} onChange={() => setScope([])} />
                    <span>Todos os documentos prontos</span>
                  </label>
                  {pickable.map((d) => (
                    <label key={d.id} className="check">
                      <input type="checkbox" checked={scope.includes(d.id)}
                        onChange={(e) => setScope(e.target.checked ? [...scope, d.id] : scope.filter((x) => x !== d.id))} />
                      <span>{d.title}</span>
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
                  <p>O Nexo responde só com o que está nos documentos indexados e mostra a página de cada resposta.</p>
                  <Link className="button button--primary" to="/documentos"><Icon name="upload" size={16} />Enviar PDFs</Link>
                </>
              ) : (
                <>
                  <h2>O que você precisa encontrar?</h2>
                  <p>
                    Pergunte sobre {scoped.length ? plural(scoped.length, "o documento escolhido", "os documentos escolhidos")
                      : plural(ready.length, "documento pronto", "documentos prontos")}. Cada afirmação da resposta
                    aponta o trecho e a página de onde saiu.
                  </p>
                  <ul className="empty__tips">
                    <li><b>Use os termos do manual.</b> Nomes de peças, códigos de erro e unidades ajudam a busca.</li>
                    <li><b>Continue a conversa.</b> “E o passo seguinte?” é entendido com o histórico.</li>
                    <li><b>Limite o escopo</b> em “Escolher documentos” quando os PDFs tratarem de produtos parecidos.</li>
                  </ul>
                </>
              )}
            </div>
          )}
          {items.map((m, index) =>
            m.role === "user" ? (
              <h2 key={m.id} className="q">{m.content}</h2>
            ) : (
              <div key={m.id} className={`a${m.answered === false ? " a--missing" : ""}`}>
                {m.answered === false ? (
                  <div className="missing">
                    <p className="missing__title">{m.content}</p>
                    <p>Nenhum trecho passou nos cortes de relevância, então o modelo não foi chamado.</p>
                    <div className="missing__actions">
                      <Link className="button button--small" to={`/busca?q=${encodeURIComponent(items[index - 1]?.content ?? "")}`}>
                        <Icon name="search" size={15} />Ver trechos parecidos
                      </Link>
                      {scope.length > 0 && (
                        <button className="button button--small" onClick={() => setScope([])}>Consultar todos os documentos</button>
                      )}
                      <Link className="button button--small" to="/documentos"><Icon name="upload" size={15} />Enviar outro PDF</Link>
                    </div>
                  </div>
                ) : (
                  <AnswerText text={m.content} sources={m.sources.length}
                    active={selection?.messageId === m.id ? selection.rank : null}
                    onCite={(rank) => setSelection({ messageId: m.id, rank })} />
                )}
                {m.sources.length > 0 && (
                  <div className="a__refs" aria-label="Páginas citadas">
                    {m.sources.map((s) => (
                      <button key={s.rank} className={`ref${selection?.messageId === m.id && selection.rank === s.rank ? " ref--on" : ""}`}
                        onClick={() => setSelection({ messageId: m.id, rank: s.rank })} title={s.document_title}>
                        <span className="ref__n">{s.rank}</span>
                        <span className="ref__doc">{s.document_title}</span>
                        <span className="ref__p">p. {s.page}</span>
                      </button>
                    ))}
                  </div>
                )}
                <footer className="a__foot">
                  {m.grounded === false && <span className="warn">A verificação automática não confirmou todos os pontos.</span>}
                  {m.grounded === true && m.model !== "extrativo" && <span className="ok">Verificada contra os trechos</span>}
                  <span className="a__meta" title={formatDateTime(m.created_at)}>
                    {m.model}{m.latency_ms !== null ? `, ${(m.latency_ms / 1000).toFixed(1).replace(".", ",")} s` : ""}
                  </span>
                  <span className="a__actions">
                    <button className="icon-button" aria-label="Copiar resposta com as fontes" title="Copiar com as fontes" onClick={() => copy(m)}>
                      <Icon name={copied === m.id ? "check" : "copy"} size={16} />
                    </button>
                    <button className={`icon-button${m.my_rating === 1 ? " is-on" : ""}`} aria-pressed={m.my_rating === 1}
                      aria-label="Resposta útil" title="Resposta útil" onClick={() => rate(m, 1)}>
                      <Icon name="up" size={16} />
                    </button>
                    <button className={`icon-button${m.my_rating === -1 ? " is-on" : ""}`} aria-pressed={m.my_rating === -1}
                      aria-label="Resposta não ajudou" title="Não ajudou" onClick={() => rate(m, -1)}>
                      <Icon name="down" size={16} />
                    </button>
                  </span>
                </footer>
              </div>
            ),
          )}
          {pending && (
            <>
              <h2 className="q">{pending}</h2>
              <div className="a a--pending" role="status">
                <span className="reading" aria-hidden="true"><i /><i /><i /></span>
                <p>Lendo os trechos mais próximos da pergunta…</p>
              </div>
            </>
          )}
          <div ref={bottom} />
        </div>

        <div className="composer-wrap">
          {error && <p className="alert" role="alert">{error}</p>}
          <form className="composer" onSubmit={submit}>
            <textarea ref={textarea} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey}
              placeholder={ready.length ? "Pergunte algo sobre os documentos" : "Envie um PDF em Documentos para perguntar"}
              aria-label="Pergunta" rows={1} maxLength={4000} disabled={!!pending} />
            <button className="send" type="submit" disabled={!question.trim() || !!pending || ready.length === 0} aria-label="Enviar pergunta">
              <Icon name="send" />
            </button>
          </form>
          <p className="composer__hint"><kbd>Enter</kbd> envia, <kbd>Shift</kbd> + <kbd>Enter</kbd> quebra a linha, <kbd>Ctrl</kbd> + <kbd>K</kbd> abre a paleta.</p>
        </div>
      </section>

      {selectedMessage && (
        <SourcesPanel sources={selectedMessage.sources} query={selectedQuery} active={selection?.rank ?? null}
          onSelect={(rank) => setSelection({ messageId: selectedMessage.id, rank })}
          onClose={() => setSelection(null)} onError={(msg) => toast(msg, "error")} />
      )}
    </div>
  );
}
