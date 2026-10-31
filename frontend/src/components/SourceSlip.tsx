import { forwardRef } from "react";
import { openDocument, type ApiError, type Source } from "../api";
import { formatScore } from "../format";
import { Highlight } from "./Highlight";
import { Icon } from "./Icon";

interface Props {
  source: Source;
  query: string;
  active?: boolean;
  onSelect?: () => void;
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

export const SourceSlip = forwardRef<HTMLElement, Props>(function SourceSlip({ source: s, query, active, onSelect, onError }, ref) {
  const isPdf = !s.kind || s.kind === "pdf";
  return (
    <article ref={ref} className={`source${active ? " source--active" : ""}`} onClick={onSelect}>
      <div className="source__page">
        <span className="source__rank">{s.rank}</span>
        <span className="source__num">{s.page}</span>
        <span className="source__label">{isPdf ? "página" : "parte"}</span>
      </div>
      <div className="source__body">
        <h3>{s.document_title}</h3>
        <blockquote><Highlight text={s.excerpt} query={query} /></blockquote>
        <Meter label="Similaridade" value={s.similarity} />
        <Meter label="Reranking" value={s.rerank_score} />
        {s.document_id && isPdf && (
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
  );
});
