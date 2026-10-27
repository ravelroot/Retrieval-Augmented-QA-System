import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../store";
import { Icon } from "./Icon";

interface Item {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: string;
  run: () => void;
}

function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function CommandPalette({ onClose, onTheme }: { onClose: () => void; onTheme: () => void }) {
  const navigate = useNavigate();
  const { conversations, documents } = useStore();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => input.current?.focus(), []);

  const go = (to: string) => () => { navigate(to); onClose(); };

  const items = useMemo<Item[]>(() => {
    const base: Item[] = [
      { id: "new", group: "Ações", label: "Nova conversa", icon: "plus", run: go("/conversas") },
      { id: "search", group: "Ações", label: "Buscar nos trechos", icon: "search", run: go("/busca") },
      { id: "upload", group: "Ações", label: "Enviar PDFs", icon: "upload", run: go("/documentos") },
      { id: "theme", group: "Ações", label: "Trocar o tema", icon: "auto", run: () => { onTheme(); onClose(); } },
      { id: "nav-docs", group: "Ir para", label: "Documentos", icon: "docs", run: go("/documentos") },
      { id: "nav-metrics", group: "Ir para", label: "Painel de qualidade", icon: "chart", run: go("/painel") },
      { id: "nav-int", group: "Ir para", label: "Integrações", icon: "plug", run: go("/integracoes") },
      { id: "nav-sys", group: "Ir para", label: "Sistema e conta", icon: "system", run: go("/sistema") },
    ];
    const convs: Item[] = conversations.slice(0, 40).map((c) => ({
      id: `c-${c.id}`, group: "Conversas", label: c.title, icon: "chat", run: go(`/conversas/${c.id}`),
    }));
    const docs: Item[] = documents.filter((d) => d.status === "READY").map((d) => ({
      id: `d-${d.id}`, group: "Perguntar a um documento", label: d.title, hint: `${d.pages} p.`, icon: "docs",
      run: go(`/conversas?documento=${d.id}`),
    }));
    const all = [...base, ...convs, ...docs];
    const q = fold(query.trim());
    if (!q) return [...base, ...convs.slice(0, 5)];
    return all.filter((i) => fold(i.label).includes(q)).slice(0, 30);
  }, [query, conversations, documents]);

  useEffect(() => setCursor(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${cursor}"]`)?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(items.length - 1, c + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); items[cursor]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  }

  let lastGroup = "";
  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Paleta de comandos" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette__input">
          <Icon name="search" />
          <input ref={input} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKey}
            placeholder="Ir para, abrir conversa ou perguntar a um documento" aria-label="Comando"
            role="combobox" aria-expanded="true" aria-controls="palette-list"
            aria-activedescendant={items[cursor] ? `cmd-${items[cursor].id}` : undefined} />
          <kbd>Esc</kbd>
        </div>
        <ul className="palette__list" id="palette-list" role="listbox" ref={listRef}>
          {items.length === 0 && <li className="palette__empty">Nada encontrado para “{query}”.</li>}
          {items.map((item, index) => {
            const header = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            return (
              <li key={item.id} role="presentation">
                {header && <span className="palette__group">{header}</span>}
                <button id={`cmd-${item.id}`} role="option" aria-selected={index === cursor} data-index={index}
                  className="palette__item" onMouseMove={() => setCursor(index)} onClick={item.run}>
                  <Icon name={item.icon} size={16} />
                  <span>{item.label}</span>
                  {item.hint && <small>{item.hint}</small>}
                </button>
              </li>
            );
          })}
        </ul>
        <footer className="palette__foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> navegar</span>
          <span><kbd>Enter</kbd> abrir</span>
        </footer>
      </div>
    </div>
  );
}
