import { useEffect, useRef } from "react";
import { Icon } from "./Icon";

const GROUPS: { title: string; keys: [string[], string][] }[] = [
  {
    title: "Em qualquer tela",
    keys: [
      [["Ctrl", "K"], "Abre a paleta de comandos"],
      [["?"], "Mostra estes atalhos"],
      [["Alt", "N"], "Nova conversa"],
      [["Alt", "B"], "Busca nos trechos"],
      [["Alt", "D"], "Documentos"],
      [["Alt", "W"], "WhatsApp"],
    ],
  },
  {
    title: "Na conversa",
    keys: [
      [["Enter"], "Envia a pergunta"],
      [["Shift", "Enter"], "Quebra a linha"],
      [["Esc"], "Interrompe a resposta"],
      [["/"], "Volta para a caixa de pergunta"],
    ],
  },
  {
    title: "Paleta e tutorial",
    keys: [
      [["↑", "↓"], "Navegam na paleta"],
      [["Enter"], "Abre o item escolhido"],
      [["←", "→"], "Voltam e avançam no tutorial"],
      [["Esc"], "Fecha a paleta, o tutorial e os painéis"],
    ],
  },
];

export function ShortcutsDialog({ onClose }: { onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div ref={box} tabIndex={-1} className="palette shortcuts" role="dialog" aria-modal="true" aria-label="Atalhos de teclado"
        onMouseDown={(e) => e.stopPropagation()}>
        <header className="shortcuts__head">
          <h2 className="fina">Atalhos de teclado</h2>
          <button className="icon-button" onClick={onClose} aria-label="Fechar"><Icon name="close" /></button>
        </header>
        <div className="shortcuts__body">
          {GROUPS.map((g) => (
            <section key={g.title}>
              <h3>{g.title}</h3>
              <dl>
                {g.keys.map(([keys, label]) => (
                  <div key={`${g.title}-${label}`}>
                    <dt>{keys.map((k) => <kbd key={k}>{k}</kbd>)}</dt>
                    <dd>{label}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
