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

function Score({ label, value }: { label: string; value: number | null }) {
  const width = value === null ? 0 : Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="score" title={value === null ? `${label}: não calculado` : `${label}: ${formatScore(value)}`}>
      <span className="score__label">{label}</span>
      <span className="score__track"><span style={{ width: `${width}%` }} /></span>
      <span className="score__value">{value === null ? "—" : formatScore(value)}</span>
    </div>
  );
}

export const SourceSlip = forwardRef<HTMLElement, Props>(function SourceSlip({ source: s, query, active, onSelect, onError }, ref) {
  return (
    <article ref={ref} className={`slip${active ? " slip--active" : ""}`} onClick={onSelect}>
      <div className="slip__tab" aria-label={`Trecho ${s.rank}, página ${s.page}`}>
        <span className="slip__rank">{s.rank}</span>
        <span className="slip__p">p.</span>
        <span className="slip__page">{s.page}</span>
      </div>
      <div className="slip__body">
        <h3 className="slip__doc">{s.document_title}</h3>
        <p className="slip__text"><Highlight text={s.excerpt} query={query} /></p>
        <div className="slip__foot">
          <Score label="Similaridade" value={s.similarity} />
          <Score label="Reranking" value={s.rerank_score} />
          {s.document_id && (
            <button type="button" className="text-button" onClick={(e) => {
              e.stopPropagation();
              openDocument(s.document_id!, s.page).catch((err: ApiError) => onError(err.message));
            }}>
              <Icon name="open" size={15} />
              Abrir na página {s.page}
            </button>
          )}
        </div>
      </div>
    </article>
  );
});
