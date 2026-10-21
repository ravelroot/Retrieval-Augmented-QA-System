import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { ApiError, api, openDocument, type DocumentItem } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatSize, plural } from "../format";

export function DocumentsPage() {
  const { user } = useAuth();
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api.documents().then(setDocs).catch((e: ApiError) => setNotice({ kind: "error", text: e.message }));
  }, []);

  useEffect(load, [load]);

  const working = docs?.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [working, load]);

  async function send(list: FileList | File[]) {
    const files = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf");
    if (!files.length) {
      setNotice({ kind: "error", text: "Escolha arquivos PDF." });
      return;
    }
    setUploading(true);
    setNotice(null);
    try {
      const created = await api.upload(files);
      setNotice({ kind: "ok", text: `${plural(created.length, "PDF enviado", "PDFs enviados")}. A indexação começa em seguida.` });
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

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Documentos</h1>
          <p className="page__lead">
            {docs === null ? "Carregando…" : docs.length === 0
              ? "Nenhum PDF enviado ainda."
              : `${plural(ready.length, "documento pronto", "documentos prontos")}, ${plural(pages, "página", "páginas")} e ${plural(chunks, "trecho indexado", "trechos indexados")}.`}
          </p>
        </div>
      </header>

      <div
        className={`dropzone${dragging ? " dropzone--active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <Icon name="upload" size={28} />
        <div>
          <strong>{uploading ? "Enviando…" : "Arraste PDFs para cá"}</strong>
          <p>Manuais técnicos e livros com texto selecionável. PDFs digitalizados precisam de OCR antes.</p>
        </div>
        <button className="primary-button" onClick={() => input.current?.click()} disabled={uploading}>
          Escolher PDFs
        </button>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
          onChange={(e) => e.target.files && send(e.target.files)} />
      </div>

      {notice && <p className={notice.kind === "ok" ? "alert alert--ok" : "alert"} role="status">{notice.text}</p>}

      {docs && docs.length > 0 && (
        <ul className="doc-list">
          {docs.map((doc) => (
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
                  <span>{doc.filename}</span>
                  <span>{formatSize(doc.size_bytes)}</span>
                  {doc.status === "READY" && <span>{plural(doc.pages, "página", "páginas")}</span>}
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
                    <button className="icon-button" title="Abrir PDF" aria-label={`Abrir ${doc.title}`}
                      onClick={() => openDocument(doc.id).catch((e: ApiError) => setNotice({ kind: "error", text: e.message }))}>
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
    </div>
  );
}
