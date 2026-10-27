import { useEffect, useRef } from "react";
import type { Source } from "../api";
import { Icon } from "./Icon";
import { SourceSlip } from "./SourceSlip";

interface Props {
  sources: Source[];
  query: string;
  active: number | null;
  onSelect: (rank: number) => void;
  onClose: () => void;
  onError: (message: string) => void;
}

export function SourcesPanel({ sources, query, active, onSelect, onClose, onError }: Props) {
  const refs = useRef<Record<number, HTMLElement | null>>({});

  useEffect(() => {
    if (active !== null) refs.current[active]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  return (
    <aside className="sources" aria-label="Trechos usados na resposta">
      <header className="sources__head">
        <div>
          <h2>Trechos usados</h2>
          <p>O que o Nexo leu nos PDFs para responder. Os termos da pergunta aparecem destacados.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Fechar trechos">
          <Icon name="close" />
        </button>
      </header>
      <ol className="sources__list">
        {sources.map((s) => (
          <li key={s.rank}>
            <SourceSlip ref={(el) => { refs.current[s.rank] = el; }} source={s} query={query}
              active={active === s.rank} onSelect={() => onSelect(s.rank)} onError={onError} />
          </li>
        ))}
      </ol>
    </aside>
  );
}
