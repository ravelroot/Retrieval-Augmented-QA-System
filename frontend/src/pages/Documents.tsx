import { useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, openDocument, type DocumentItem, type DocumentStatus } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { formatDateTime, formatSize, plural } from "../format";
import { useStore } from "../store";

type Sort = "recent" | "title" | "pages";

function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function DocumentsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { documents: docs, reloadDocuments: load } = useStore();
  const [loaded, setLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [sort, setSort] = useState<Sort>("recent");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { load(); setLoaded(true); }, [load]);

  const working = docs.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [working, load]);

  async function send(list: FileList | File[]) {
    const files = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf");
    if (!files.length) {
      toast("Escolha arquivos PDF.", "error");
      return;
    }
    setUploading(true);
    try {
      const created = await api.upload(files);
      toast(`${plural(created.length, "PDF enviado", "PDFs enviados")}. A indexação começa em seguida.`);
      load();
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) void send(e.dataTransfer.files);
  }

  async function act(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      toast(done);
      load();
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  async function rename(e: FormEvent, doc: DocumentItem) {
    e.preventDefault();
    if (!title.trim() || title.trim() === doc.title) {
      setEditing(null);
      return;
    }
    await act(() => api.renameDocument(doc.id, title.trim()), "Título alterado. O documento será reindexado com o novo nome.");
    setEditing(null);
  }

  const ready = docs.filter((d) => d.status === "READY");
  const pages = ready.reduce((sum, d) => sum + d.pages, 0);
  const chunks = ready.reduce((sum, d) => sum + d.chunks, 0);
  const queued = docs.filter((d) => d.status === "PENDING" || d.status === "PROCESSING").length;
  const failed = docs.filter((d) => d.status === "FAILED").length;

  const visible = useMemo(() => {
    const q = fold(filter.trim());
    const list = docs.filter((d) => (!status || d.status === status) && (!q || fold(`${d.title} ${d.filename}`).includes(q)));
    if (sort === "title") return [...list].sort((a, b) => a.title.localeCompare(b.title, "pt-BR"));
    if (sort === "pages") return [...list].sort((a, b) => b.pages - a.pages);
    return list;
  }, [docs, filter, status, sort]);

  return (
    <div className="page">
      <header className="page__head page__head--row">
        <div>
          <h1>Documentos</h1>
          <p className="page__lead">Os PDFs que o Nexo consulta. Só os documentos prontos entram nas respostas.</p>
        </div>
        <button className="button button--primary" onClick={() => input.current?.click()} disabled={uploading}>
          <Icon name="upload" size={16} />
          {uploading ? "Enviando…" : "Enviar PDFs"}
        </button>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
          onChange={(e) => e.target.files && send(e.target.files)} />
      </header>

      <dl className="ledger" aria-label="Resumo do acervo">
        <div><dt>Documentos prontos</dt><dd>{ready.length}</dd></div>
        <div><dt>Páginas lidas</dt><dd>{pages.toLocaleString("pt-BR")}</dd></div>
        <div><dt>Trechos indexados</dt><dd>{chunks.toLocaleString("pt-BR")}</dd></div>
        <div className={queued ? "is-busy" : ""}><dt>Na fila</dt><dd>{queued}</dd></div>
        <div className={failed ? "is-bad" : ""}><dt>Com falha</dt><dd>{failed}</dd></div>
      </dl>

      <div
        className={`dropzone${dragging ? " dropzone--active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <Icon name="upload" size={20} />
        <p>
          <b>{uploading ? "Enviando…" : "Arraste PDFs para cá"}</b> ou{" "}
          <button className="text-button" onClick={() => input.current?.click()} disabled={uploading}>escolha no computador</button>.
          {" "}Manuais e livros com texto selecionável; PDFs digitalizados precisam de OCR antes.
        </p>
      </div>

      {docs.length > 0 && (
        <div className="toolbar">
          <input className="toolbar__search" value={filter} onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrar por título ou arquivo" aria-label="Filtrar documentos" />
          <label className="select select--inline">
            <span>Situação</span>
            <select value={status} onChange={(e) => setStatus(e.target.value as DocumentStatus | "")}>
              <option value="">Todas</option>
              <option value="READY">Prontos</option>
              <option value="PROCESSING">Indexando</option>
              <option value="PENDING">Na fila</option>
              <option value="FAILED">Com falha</option>
            </select>
          </label>
          <label className="select select--inline">
            <span>Ordem</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="recent">Mais recentes</option>
              <option value="title">Título</option>
              <option value="pages">Mais páginas</option>
            </select>
          </label>
        </div>
      )}

      {loaded && docs.length === 0 && (
        <div className="empty empty--page">
          <h2>O acervo está vazio</h2>
          <p>Envie o primeiro manual. Ele é dividido em trechos, indexado e fica pronto para perguntas em segundos.</p>
        </div>
      )}

      {visible.length > 0 && (
        <ul className="doc-list">
          {visible.map((doc) => (
            <li key={doc.id} className={`doc doc--${doc.status.toLowerCase()}`}>
              <div className="doc__main">
                {editing === doc.id ? (
                  <form className="inline-form" onSubmit={(e) => rename(e, doc)}>
                    <input aria-label="Novo título" value={title} autoFocus maxLength={200}
                      onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setEditing(null)} />
                    <button className="button button--primary button--small" type="submit">Salvar</button>
                    <button className="button button--small" type="button" onClick={() => setEditing(null)}>Cancelar</button>
                  </form>
                ) : (
                  <h2 className="doc__title">{doc.title}</h2>
                )}
                <p className="doc__meta">
                  <span>{doc.filename}</span>
                  <span>{formatSize(doc.size_bytes)}</span>
                  {doc.status === "READY" && <span>{plural(doc.pages, "página", "páginas")}</span>}
                  {doc.status === "READY" && <span>{plural(doc.chunks, "trecho", "trechos")}</span>}
                  <span>Enviado por {doc.uploaded_by === user?.username ? "você" : doc.uploaded_by} em {formatDateTime(doc.created_at)}</span>
                </p>
                {doc.status === "FAILED" && doc.error && <p className="doc__error">{doc.error}</p>}
                {(doc.status === "PENDING" || doc.status === "PROCESSING") && <div className="progress" aria-hidden="true"><span /></div>}
              </div>
              <StatusBadge status={doc.status} />
              <div className="doc__actions">
                {confirming === doc.id ? (
                  <>
                    <span className="doc__confirm">Excluir o PDF e os trechos?</span>
                    <button className="button button--danger button--small" onClick={() => { setConfirming(null); void act(() => api.deleteDocument(doc.id), "Documento excluído."); }}>
                      Excluir
                    </button>
                    <button className="button button--small" onClick={() => setConfirming(null)}>Manter</button>
                  </>
                ) : (
                  <>
                    {doc.status === "READY" && (
                      <Link className="icon-button" title="Perguntar a este documento" aria-label={`Perguntar a ${doc.title}`}
                        to={`/conversas?documento=${doc.id}`}>
                        <Icon name="chat" />
                      </Link>
                    )}
                    <button className="icon-button" title="Abrir PDF" aria-label={`Abrir ${doc.title}`}
                      onClick={() => openDocument(doc.id).catch((e: ApiError) => toast(e.message, "error"))}>
                      <Icon name="open" />
                    </button>
                    {doc.can_delete && (
                      <>
                        <button className="icon-button" title="Renomear" aria-label={`Renomear ${doc.title}`}
                          onClick={() => { setEditing(doc.id); setTitle(doc.title); }}>
                          <Icon name="edit" />
                        </button>
                        <button className="icon-button" title="Reindexar" aria-label={`Reindexar ${doc.title}`}
                          disabled={doc.status === "PENDING" || doc.status === "PROCESSING"}
                          onClick={() => act(() => api.reindexDocument(doc.id), "Reindexação iniciada.")}>
                          <Icon name="refresh" />
                        </button>
                        <button className="icon-button" title="Excluir" aria-label={`Excluir ${doc.title}`}
                          onClick={() => setConfirming(doc.id)}>
                          <Icon name="trash" />
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {docs.length > 0 && visible.length === 0 && <p className="muted">Nenhum documento com esses filtros.</p>}
    </div>
  );
}
