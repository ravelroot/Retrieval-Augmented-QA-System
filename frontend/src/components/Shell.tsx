import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api, type User } from "../api";
import { useAuth } from "../auth";
import { applyTheme, initialTheme, watchSystemTheme, type ThemeChoice } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Icon } from "./Icon";
import { Brand } from "./Logo";
import { Tutorial } from "./Tutorial";

export const TUTORIAL_EVENT = "nexo:tutorial";

export function openTutorial(): void {
  window.dispatchEvent(new Event(TUTORIAL_EVENT));
}

const groups = [
  {
    title: "Consulta",
    links: [
      { to: "/conversas", label: "Conversas", icon: "chat" },
      { to: "/busca", label: "Busca nos trechos", icon: "search" },
      { to: "/documentos", label: "Documentos", icon: "docs" },
    ],
  },
  {
    title: "Agentes",
    links: [
      { to: "/chats", label: "Chats com agentes", icon: "chats" },
      { to: "/agentes", label: "Agentes", icon: "bot" },
      { to: "/bases", label: "Bases de conhecimento", icon: "base" },
    ],
  },
  {
    title: "Atendimento",
    links: [{ to: "/whatsapp", label: "WhatsApp", icon: "whatsapp" }],
  },
  {
    title: "Gestão",
    links: [
      { to: "/painel", label: "Painel de qualidade", icon: "chart" },
      { to: "/integracoes", label: "Integrações", icon: "plug" },
    ],
  },
  {
    title: "Conta",
    links: [{ to: "/sistema", label: "Sistema e conta", icon: "system" }],
  },
];

const themeLabel: Record<ThemeChoice, { label: string; icon: string }> = {
  light: { label: "Tema claro", icon: "sun" },
  dark: { label: "Tema escuro", icon: "moon" },
  auto: { label: "Tema automático", icon: "auto" },
};

const nextTheme: Record<ThemeChoice, ThemeChoice> = { light: "dark", dark: "auto", auto: "light" };

export function Shell({ children }: { children: ReactNode }) {
  const { user, signOut, updateUser } = useAuth();
  const [theme, setTheme] = useState<ThemeChoice>(initialTheme);
  const [open, setOpen] = useState(false);
  const [palette, setPalette] = useState(false);
  const [tutorial, setTutorial] = useState(() => !!user && !user.tutorial_done_at);
  const location = useLocation();

  useEffect(() => {
    const show = () => { setPalette(false); setOpen(false); setTutorial(true); };
    window.addEventListener(TUTORIAL_EVENT, show);
    return () => window.removeEventListener(TUTORIAL_EVENT, show);
  }, []);

  function finishTutorial() {
    setTutorial(false);
    if (user && !user.tutorial_done_at) {
      updateUser({ ...user, tutorial_done_at: new Date().toISOString() });
      api.tutorial(true).then((u: User) => updateUser(u)).catch(() => undefined);
    }
  }

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => (theme === "auto" ? watchSystemTheme(() => applyTheme("auto")) : undefined), [theme]);
  useEffect(() => { setOpen(false); setPalette(false); }, [location.pathname, location.search]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const initials = (user?.name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

  return (
    <div className={`shell${open ? " shell--open" : ""}`}>
      <header className="topbar">
        <button className="icon-button" onClick={() => setOpen(true)} aria-label="Abrir menu">
          <Icon name="menu" />
        </button>
        <Brand subtitle="" />
        <button className="icon-button topbar__palette" onClick={() => setPalette(true)} aria-label="Abrir paleta de comandos">
          <Icon name="search" />
        </button>
      </header>
      <aside className="rail" aria-label="Navegação principal">
        <div className="rail__head">
          <Brand />
          <button className="icon-button rail__close" onClick={() => setOpen(false)} aria-label="Fechar menu">
            <Icon name="close" />
          </button>
        </div>
        <button className="rail__palette" onClick={() => setPalette(true)}>
          <Icon name="search" size={16} />
          <span>Ir para…</span>
          <kbd>Ctrl K</kbd>
        </button>
        <nav className="rail__nav">
          {groups.map((group) => (
            <div key={group.title} className="rail__group">
              <span className="rail__group-title">{group.title}</span>
              {group.links.map((link) => (
                <NavLink key={link.to} to={link.to} className="rail__link">
                  <Icon name={link.icon} />
                  <span>{link.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="rail__foot">
          <div className="rail__actions">
            <button className="rail__link" onClick={() => setTutorial(true)} title="Rever o tutorial">
              <Icon name="help" />
              <span>Tutorial</span>
            </button>
            <button className="rail__link" onClick={() => setTheme(nextTheme[theme])} title="Alternar entre claro, escuro e automático">
              <Icon name={themeLabel[theme].icon} />
              <span>{themeLabel[theme].label}</span>
            </button>
            <button className="rail__link" onClick={signOut}>
              <Icon name="logout" />
              <span>Sair</span>
            </button>
          </div>
          <div className="rail__user">
            <span className="avatar" aria-hidden="true">{initials || "?"}</span>
            <span>
              <strong>{user?.name}</strong>
              <small>{user?.role === "admin" ? "Administrador" : "Usuário"} · {user?.username}</small>
            </span>
          </div>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <main className="stage">{children}</main>
      {palette && <CommandPalette onClose={() => setPalette(false)} onTheme={() => setTheme(nextTheme[theme])}
        onTutorial={() => { setPalette(false); setTutorial(true); }} />}
      {tutorial && <Tutorial name={user?.name ?? ""} onDone={finishTutorial} />}
    </div>
  );
}
