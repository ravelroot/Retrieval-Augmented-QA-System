import { useEffect, useRef } from "react";
import type { Source } from "../api";
import { plural } from "../format";
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
    <aside className="sources" aria-label="Trechos citados na resposta">
      <header className="sources__head">
        <div>
          <h2>Trechos citados</h2>
          <p>{plural(sources.length, "trecho lido", "trechos lidos")} para responder. Em amarelo, os termos da pergunta.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Fechar trechos">
          <Icon name="close" />
        </button>
      </header>
      <div className="sources__list">
        {sources.map((s) => (
          <SourceSlip key={s.rank} ref={(el) => { refs.current[s.rank] = el; }} source={s} query={query}
            active={active === s.rank} onSelect={() => onSelect(s.rank)} onError={onError} />
        ))}
      </div>
    </aside>
  );
}
