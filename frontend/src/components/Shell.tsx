import { useCallback, useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ApiError, api, type User } from "../api";
import { useAuth } from "../auth";
import { applyTheme, initialTheme, watchSystemTheme, type ThemeChoice } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Icon } from "./Icon";
import { Brand } from "./Logo";
import { ShortcutsDialog } from "./Shortcuts";
import { Tutorial } from "./Tutorial";

export const TUTORIAL_EVENT = "nexo:tutorial";
export const SHORTCUTS_EVENT = "nexo:atalhos";

export function openTutorial(): void {
  window.dispatchEvent(new Event(TUTORIAL_EVENT));
}

export function openShortcuts(): void {
  window.dispatchEvent(new Event(SHORTCUTS_EVENT));
}

function typing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

const JUMPS: Record<string, string> = { n: "/conversas", b: "/busca", d: "/documentos", w: "/whatsapp" };

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
  const [shortcuts, setShortcuts] = useState(false);
  const [waiting, setWaiting] = useState(0);
  const [offline, setOffline] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const show = () => { setPalette(false); setOpen(false); setTutorial(true); };
    const keys = () => { setPalette(false); setShortcuts(true); };
    window.addEventListener(TUTORIAL_EVENT, show);
    window.addEventListener(SHORTCUTS_EVENT, keys);
    return () => {
      window.removeEventListener(TUTORIAL_EVENT, show);
      window.removeEventListener(SHORTCUTS_EVENT, keys);
    };
  }, []);

  const ping = useCallback(() => {
    api.waSummary()
      .then((s) => { setWaiting(s.waiting); setOffline(false); })
      .catch((e: ApiError) => setOffline(e.code === "NETWORK"));
  }, []);

  useEffect(() => {
    ping();
    const timer = window.setInterval(ping, offline ? 8000 : 30000);
    const goOffline = () => setOffline(true);
    window.addEventListener("online", ping);
    window.addEventListener("offline", goOffline);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", ping);
      window.removeEventListener("offline", goOffline);
    };
  }, [ping, offline]);

  useEffect(() => { ping(); }, [location.pathname]);

  useEffect(() => {
    document.title = waiting > 0 ? `(${waiting}) Nexo` : "Nexo";
  }, [waiting]);

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
        return;
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey && JUMPS[e.key.toLowerCase()]) {
        e.preventDefault();
        navigate(JUMPS[e.key.toLowerCase()]);
        return;
      }
      if (e.key === "?" && !e.ctrlKey && !e.metaKey && !e.altKey && !typing(e.target)) {
        e.preventDefault();
        setShortcuts((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

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
                  {link.to === "/whatsapp" && waiting > 0 && (
                    <span className="rail__badge" aria-label={`${waiting} aguardando atendente`} title="Clientes aguardando atendente">{waiting}</span>
                  )}
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
            <button className="rail__link" onClick={() => setShortcuts(true)} title="Atalhos de teclado (?)">
              <Icon name="command" />
              <span>Atalhos</span>
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
      <main className="stage">
        {offline && (
          <div className="offline" role="alert">
            <span>Sem conexão com o servidor do Nexo. O que você digitar continua aqui; tentando de novo a cada poucos segundos.</span>
            <button className="ghost-button small" onClick={ping}>Tentar agora</button>
          </div>
        )}
        {children}
      </main>
      {palette && <CommandPalette onClose={() => setPalette(false)} onTheme={() => setTheme(nextTheme[theme])}
        onTutorial={() => { setPalette(false); setTutorial(true); }}
        onShortcuts={() => { setPalette(false); setShortcuts(true); }} />}
      {tutorial && <Tutorial name={user?.name ?? ""} onDone={finishTutorial} />}
      {shortcuts && <ShortcutsDialog onClose={() => setShortcuts(false)} />}
    </div>
  );
}
