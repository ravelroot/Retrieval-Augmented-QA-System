import { useEffect, useRef } from "react";
import { openDocument, type ApiError, type Source } from "../api";
import { formatScore } from "../format";
import { Icon } from "./Icon";

interface Props {
  sources: Source[];
  active: number | null;
  onSelect: (rank: number) => void;
  onClose: () => void;
  onError: (message: string) => void;
}

function Meter({ label, value }: { label: string; value: number | null }) {
  const width = value === null ? 0 : Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="meter">
      <span>{label}</span>
      <span className="meter__track"><span style={{ width: `${width}%` }} /></span>
      <span className="meter__value">{formatScore(value)}</span>
    </div>
  );
}

export function SourcesPanel({ sources, active, onSelect, onClose, onError }: Props) {
  const refs = useRef<Record<number, HTMLElement | null>>({});

  useEffect(() => {
    if (active !== null) refs.current[active]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  return (
    <aside className="sources" aria-label="Trechos usados na resposta">
      <header className="sources__head">
        <div>
          <h2>Trechos usados</h2>
          <p>O que o Nexo leu nos PDFs para responder.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Fechar trechos">
          <Icon name="close" />
        </button>
      </header>
      <ol className="sources__list">
        {sources.map((s) => (
          <li key={s.rank}>
            <article
              ref={(el) => { refs.current[s.rank] = el; }}
              className={`source${active === s.rank ? " source--active" : ""}`}
              onClick={() => onSelect(s.rank)}
            >
              <div className="source__page">
                <span className="source__rank">{s.rank}</span>
                <span className="source__num">{s.page}</span>
                <span className="source__label">página</span>
              </div>
              <div className="source__body">
                <h3>{s.document_title}</h3>
                <blockquote>{s.excerpt}</blockquote>
                <Meter label="Similaridade" value={s.similarity} />
                <Meter label="Reranking" value={s.rerank_score} />
                {s.document_id && (
                  <button className="link-button" onClick={(e) => {
                    e.stopPropagation();
                    openDocument(s.document_id!, s.page).catch((err: ApiError) => onError(err.message));
                  }}>
                    <Icon name="open" size={16} />
                    Abrir o PDF na página {s.page}
                  </button>
                )}
              </div>
            </article>
          </li>
        ))}
      </ol>
    </aside>
  );
}
