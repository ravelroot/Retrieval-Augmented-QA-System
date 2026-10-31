import { useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, openDocument, type DocumentItem, type DocumentStatus, type KnowledgeBase } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatSize, plural } from "../format";
import { useStore } from "../store";

type Sort = "recent" | "title" | "pages";

const ACCEPT = ".pdf,.docx,.txt,.md,.csv,.json,.html,.htm,application/pdf";

export function kindLabel(doc: DocumentItem): string {
  if (doc.kind === "note") return "texto";
  return (doc.extension || "pdf").toLowerCase();
}

export function unitLabel(doc: DocumentItem, count: number): string {
  return doc.kind === "pdf" || !doc.kind ? plural(count, "página", "páginas") : plural(count, "parte", "partes");
}

function fold(text: string) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export function DocumentsPage() {
  const { user } = useAuth();
  const { documents, reloadDocuments: load } = useStore();
  const [loaded, setLoaded] = useState(false);
  const docs: DocumentItem[] | null = loaded ? documents : null;
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [sort, setSort] = useState<Sort>("recent");
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [target, setTarget] = useState("");
  const [baseFilter, setBaseFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { load(); setLoaded(true); }, [load]);
  useEffect(() => {
    api.bases().then((list) => {
      setBases(list);
      setTarget((current) => current || list.find((b) => b.is_default)?.id || list[0]?.id || "");
    }).catch(() => undefined);
  }, []);
  const baseName = useMemo(() => Object.fromEntries(bases.map((b) => [b.id, b.name])), [bases]);

  const working = docs?.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [working, load]);

  async function send(list: FileList | File[]) {
    const allowed = [".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".html", ".htm"];
    const files = Array.from(list).filter((f) => allowed.some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (!files.length) {
      setNotice({ kind: "error", text: "Escolha arquivos PDF, Word, TXT, Markdown, CSV, JSON ou HTML." });
      return;
    }
    setUploading(true);
    setNotice(null);
    try {
      const created = target ? await api.uploadToBase(target, files) : await api.upload(files);
      setNotice({ kind: "ok", text: `${plural(created.length, "arquivo enviado", "arquivos enviados")}${target && baseName[target] ? ` para ${baseName[target]}` : ""}. A indexação começa em seguida.` });
      load();
    } catch (e) {
      setNotice({ kind: "error", text: (e as ApiError).message });
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
    setNotice(null);
    try {
      await action();
      setNotice({ kind: "ok", text: done });
      load();
    } catch (e) {
      setNotice({ kind: "error", text: (e as ApiError).message });
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

  const ready = docs?.filter((d) => d.status === "READY") ?? [];
  const pages = ready.reduce((sum, d) => sum + d.pages, 0);
  const chunks = ready.reduce((sum, d) => sum + d.chunks, 0);

  const queued = docs?.filter((d) => d.status === "PENDING" || d.status === "PROCESSING").length ?? 0;
  const failed = docs?.filter((d) => d.status === "FAILED").length ?? 0;

  const visible = useMemo(() => {
    const q = fold(filter.trim());
    const list = (docs ?? []).filter((d) => (!status || d.status === status) && (!baseFilter || d.base_id === baseFilter)
      && (!q || fold(`${d.title} ${d.filename}`).includes(q)));
    if (sort === "title") return [...list].sort((a, b) => a.title.localeCompare(b.title, "pt-BR"));
    if (sort === "pages") return [...list].sort((a, b) => b.pages - a.pages);
    return list;
  }, [docs, filter, status, sort, baseFilter]);

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Acervo</span>
          <h1>Documentos</h1>
          <p className="page__lead">Tudo o que o Nexo consulta, de todas as bases de conhecimento. Só os itens prontos entram nas respostas. Para organizar por agente, use <Link to="/bases">Bases de conhecimento</Link>.</p>
        </div>
      </header>

      <div className="box box--intake">
        <section className="lid" aria-label="Resumo do acervo">
          <span className="lid__label">Trechos indexados</span>
          <strong className="lid__number">{docs === null ? "—" : chunks.toLocaleString("pt-BR")}</strong>
          <p className="lid__sub">
            {docs === null ? "Carregando…" : docs.length === 0 ? "Nenhum PDF enviado ainda."
              : `${plural(ready.length, "documento pronto", "documentos prontos")} e ${plural(pages, "página lida", "páginas lidas")}.`}
          </p>
          <dl className="lid__stats">
            <div><dt>Prontos</dt><dd>{ready.length}</dd></div>
            <div><dt>Páginas</dt><dd>{pages.toLocaleString("pt-BR")}</dd></div>
            <div><dt>Na fila</dt><dd>{queued}</dd></div>
            <div><dt>Com falha</dt><dd>{failed}</dd></div>
          </dl>
        </section>

        <div
          className={`dropzone${dragging ? " dropzone--active" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <span className="dropzone__icon"><Icon name="upload" size={22} /></span>
          <div>
            <strong>{uploading ? "Enviando…" : "Arraste arquivos para cá"}</strong>
            <p>PDF, Word, TXT, Markdown, CSV, JSON ou HTML com texto selecionável. PDFs digitalizados precisam de OCR antes.</p>
          </div>
          <div className="upload-target">
            {bases.length > 0 && (
              <label className="select">
                <span>Enviar para a base</span>
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  {bases.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </label>
            )}
            <button className="primary-button" onClick={() => input.current?.click()} disabled={uploading}>
              <Icon name="plus" size={16} />
              Escolher arquivos
            </button>
          </div>
          <input ref={input} type="file" accept={ACCEPT} multiple hidden
            onChange={(e) => e.target.files && send(e.target.files)} />
        </div>
      </div>

      {notice && <p className={notice.kind === "ok" ? "alert alert--ok" : "alert"} role="status">{notice.text}</p>}

      {docs && docs.length > 0 && (
        <div className="toolbar">
          <input className="toolbar__search" value={filter} onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrar por título ou arquivo" aria-label="Filtrar documentos" />
          {bases.length > 1 && (
            <label className="select">
              <span>Base</span>
              <select value={baseFilter} onChange={(e) => setBaseFilter(e.target.value)}>
                <option value="">Todas</option>
                {bases.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </label>
          )}
          <label className="select">
            <span>Situação</span>
            <select value={status} onChange={(e) => setStatus(e.target.value as DocumentStatus | "")}>
              <option value="">Todas</option>
              <option value="READY">Prontos</option>
              <option value="PROCESSING">Indexando</option>
              <option value="PENDING">Na fila</option>
              <option value="FAILED">Com falha</option>
            </select>
          </label>
          <label className="select">
            <span>Ordem</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="recent">Mais recentes</option>
              <option value="title">Título</option>
              <option value="pages">Mais páginas</option>
            </select>
          </label>
        </div>
      )}

      {docs && docs.length > 0 && visible.length === 0 && <p className="toolbar__empty">Nenhum documento com esses filtros.</p>}

      {visible.length > 0 && (
        <ul className="doc-list box">
          {visible.map((doc) => (
            <li key={doc.id} className="doc">
              <div className="doc__main">
                {editing === doc.id ? (
                  <form className="inline-form" onSubmit={(e) => rename(e, doc)}>
                    <input aria-label="Novo título" value={title} autoFocus maxLength={200}
                      onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setEditing(null)} />
                    <button className="primary-button small" type="submit">Salvar</button>
                    <button className="ghost-button small" type="button" onClick={() => setEditing(null)}>Cancelar</button>
                  </form>
                ) : (
                  <h2 className="doc__title">{doc.title}</h2>
                )}
                <p className="doc__meta">
                  <span className="kind-tag">{kindLabel(doc)}</span>
                  {baseName[doc.base_id] && <Link className="doc__base" to={`/bases/${doc.base_id}`}>{baseName[doc.base_id]}</Link>}
                  <span>{doc.filename}</span>
                  <span>{formatSize(doc.size_bytes)}</span>
                  {doc.status === "READY" && <span>{unitLabel(doc, doc.pages)}</span>}
                  {doc.status === "READY" && <span>{plural(doc.chunks, "trecho", "trechos")}</span>}
                  <span>Enviado por {doc.uploaded_by === user?.username ? "você" : doc.uploaded_by} em {formatDateTime(doc.created_at)}</span>
                </p>
                {doc.status === "FAILED" && doc.error && <p className="doc__error">{doc.error}</p>}
                {(doc.status === "PENDING" || doc.status === "PROCESSING") && <div className="busline" aria-hidden="true"><span /></div>}
              </div>
              <StatusBadge status={doc.status} />
              <div className="doc__actions">
                {confirming === doc.id ? (
                  <>
                    <span className="doc__confirm">Excluir o PDF e os trechos?</span>
                    <button className="danger-button small" onClick={() => { setConfirming(null); void act(() => api.deleteDocument(doc.id), "Documento excluído."); }}>
                      Excluir
                    </button>
                    <button className="ghost-button small" onClick={() => setConfirming(null)}>Manter</button>
                  </>
                ) : (
                  <>
                    {doc.status === "READY" && (
                      <Link className="icon-button" title="Perguntar a este documento" aria-label={`Perguntar a ${doc.title}`}
                        to={`/conversas?documento=${doc.id}`}>
                        <Icon name="chat" />
                      </Link>
                    )}
                    {doc.kind !== "note" && (
                      <button className="icon-button" title="Abrir arquivo" aria-label={`Abrir ${doc.title}`}
                        onClick={() => openDocument(doc.id).catch((e: ApiError) => setNotice({ kind: "error", text: e.message }))}>
                        <Icon name="open" />
                      </button>
                    )}
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
    </div>
  );
}
