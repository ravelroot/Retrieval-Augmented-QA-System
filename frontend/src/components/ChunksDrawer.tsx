import { useEffect, useRef, useState } from "react";
import { ApiError, api, openDocument, type ChunkPage, type DocumentKind } from "../api";
import { plural } from "../format";
import { Highlight } from "./Highlight";
import { Icon } from "./Icon";

const PAGE = 30;

interface Target {
  id: string;
  title: string;
  kind: DocumentKind;
  source_url?: string | null;
}

export function ChunksDrawer({ doc, onClose }: { doc: Target; onClose: () => void }) {
  const [page, setPage] = useState<ChunkPage | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const search = useRef<HTMLInputElement>(null);

  async function load(offset: number, q: string) {
    setBusy(true);
    setError("");
    try {
      const next = await api.chunks(doc.id, offset, PAGE, q);
      setPage((current) => (offset && current ? { ...next, items: [...current.items, ...next.items] } : next));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(0, query.trim()), query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [query, doc.id]);

  useEffect(() => {
    search.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function copy(id: string, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      window.setTimeout(() => setCopied(null), 1400);
    }).catch(() => undefined);
  }

  const unit = doc.kind === "pdf" ? "página" : "parte";
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="drawer chunks" role="dialog" aria-modal="true" aria-label={`Trechos de ${doc.title}`}
        onMouseDown={(e) => e.stopPropagation()}>
        <header className="drawer__head">
          <div>
            <span className="page__over">Trechos indexados</span>
            <h2 className="fina drawer__title" title={doc.title}>{doc.title}</h2>
            <p className="chunks__lead">
              {page ? (query.trim() ? `${plural(page.total, "trecho tem", "trechos têm")} “${query.trim()}”` : `${plural(page.total, "trecho", "trechos")} no banco vetorial`) : "Carregando…"}
              {doc.source_url && <> · <a href={doc.source_url} target="_blank" rel="noreferrer">abrir o link de origem</a></>}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fechar"><Icon name="close" /></button>
        </header>
        <div className="chunks__bar">
          <span className="chunks__search">
            <Icon name="search" size={16} />
            <input ref={search} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Procurar uma palavra nos trechos"
              aria-label="Procurar nos trechos" />
          </span>
        </div>
        <div className="chunks__list">
          {error && <p className="alert" role="alert">{error}</p>}
          {page && page.items.length === 0 && !busy && (
            <p className="panel__lead">{query.trim() ? "Nenhum trecho com essa palavra." : "Este item ainda não tem trechos. Ele aparece aqui depois da indexação."}</p>
          )}
          <ol>
            {page?.items.map((c) => (
              <li key={c.chunk_id} className="chunk">
                <header>
                  <span className="chunk__n">{c.index + 1}</span>
                  <span>{unit} {c.page}</span>
                  <span className="chunk__size">{c.text.length.toLocaleString("pt-BR")} caracteres</span>
                  <span className="chunk__tools">
                    {doc.kind === "pdf" && (
                      <button className="icon-button" title={`Abrir na página ${c.page}`} aria-label={`Abrir na página ${c.page}`}
                        onClick={() => openDocument(doc.id, c.page).catch((e: ApiError) => setError(e.message))}>
                        <Icon name="open" size={15} />
                      </button>
                    )}
                    <button className="icon-button" title="Copiar o trecho" aria-label="Copiar o trecho" onClick={() => copy(c.chunk_id, c.text)}>
                      <Icon name={copied === c.chunk_id ? "check" : "copy"} size={15} />
                    </button>
                  </span>
                </header>
                <p><Highlight text={c.text} query={query} /></p>
              </li>
            ))}
          </ol>
          {busy && <div className="busline" aria-hidden="true"><span /></div>}
          {page && page.items.length < page.total && !busy && (
            <button className="ghost-button small chunks__more" onClick={() => load(page.items.length, query.trim())}>
              Mostrar mais {Math.min(PAGE, page.total - page.items.length)}
            </button>
          )}
        </div>
      </aside>
    </div>
  );
}
