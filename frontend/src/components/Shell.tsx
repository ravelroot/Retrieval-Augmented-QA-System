import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api, type ApiError } from "../api";
import { useAuth } from "../auth";
import { formatRelative } from "../format";
import { useStore } from "../store";
import { applyTheme, initialTheme, watchSystemTheme, type ThemeChoice } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Icon } from "./Icon";
import { Brand } from "./Logo";
import { useToast } from "./Toast";

const links = [
  { to: "/conversas", label: "Conversas", icon: "chat" },
  { to: "/busca", label: "Busca nos trechos", icon: "search" },
  { to: "/documentos", label: "Documentos", icon: "docs" },
  { to: "/painel", label: "Painel de qualidade", icon: "chart" },
  { to: "/integracoes", label: "Integrações", icon: "plug" },
  { to: "/sistema", label: "Sistema e conta", icon: "system" },
];

const themes: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: "light", label: "Claro", icon: "sun" },
  { value: "dark", label: "Escuro", icon: "moon" },
  { value: "auto", label: "Automático", icon: "auto" },
];

function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function Recents() {
  const { conversations, reloadConversations } = useStore();
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);
  const activeId = location.pathname.startsWith("/conversas/") ? location.pathname.split("/")[2] : null;

  const visible = useMemo(() => {
    const q = fold(filter.trim());
    return q ? conversations.filter((c) => fold(c.title).includes(q)) : conversations;
  }, [conversations, filter]);

  async function remove(id: string) {
    try {
      await api.deleteConversation(id);
      setConfirm(null);
      reloadConversations();
      toast("Conversa apagada.");
      if (id === activeId) navigate("/conversas");
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  return (
    <section className="recents" aria-label="Conversas recentes">
      <div className="recents__head">
        <h2>Recentes</h2>
        {conversations.length > 6 && (
          <input className="recents__filter" value={filter} onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrar" aria-label="Filtrar conversas" />
        )}
      </div>
      {conversations.length === 0 ? (
        <p className="recents__empty">Suas conversas aparecem aqui.</p>
      ) : visible.length === 0 ? (
        <p className="recents__empty">Nenhuma conversa com “{filter}”.</p>
      ) : (
        <ul>
          {visible.map((c) => (
            <li key={c.id} className={`recent${c.id === activeId ? " recent--active" : ""}`}>
              {confirm === c.id ? (
                <div className="recent__confirm">
                  <span>Apagar?</span>
                  <button className="text-button text-button--danger" onClick={() => remove(c.id)}>Apagar</button>
                  <button className="text-button" onClick={() => setConfirm(null)}>Manter</button>
                </div>
              ) : (
                <>
                  <Link to={`/conversas/${c.id}`} className="recent__link" title={c.title}>
                    <span className="recent__title">{c.title}</span>
                    <span className="recent__when">{formatRelative(c.updated_at)}</span>
                  </Link>
                  <button className="icon-button recent__delete" aria-label={`Apagar ${c.title}`} onClick={() => setConfirm(c.id)}>
                    <Icon name="trash" size={15} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const [theme, setTheme] = useState<ThemeChoice>(initialTheme);
  const [open, setOpen] = useState(false);
  const [palette, setPalette] = useState(false);
  const location = useLocation();

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

  const cycleTheme = () => setTheme((t) => (t === "light" ? "dark" : t === "dark" ? "auto" : "light"));

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
        <button className="icon-button" onClick={() => setPalette(true)} aria-label="Abrir paleta de comandos">
          <Icon name="search" />
        </button>
      </header>
      <aside className="side" aria-label="Navegação principal">
        <div className="side__head">
          <Brand />
          <button className="icon-button side__close" onClick={() => setOpen(false)} aria-label="Fechar menu">
            <Icon name="close" />
          </button>
        </div>
        <div className="side__actions">
          <Link className="button button--primary side__new" to="/conversas">
            <Icon name="plus" size={16} />
            Nova conversa
          </Link>
          <button className="side__palette" onClick={() => setPalette(true)}>
            <Icon name="search" size={16} />
            <span>Ir para…</span>
            <kbd>Ctrl K</kbd>
          </button>
        </div>
        <nav className="side__nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className="side__link" end={link.to !== "/conversas"}>
              <Icon name={link.icon} />
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>
        <Recents />
        <div className="side__foot">
          <div className="theme-switch" role="radiogroup" aria-label="Tema">
            {themes.map((t) => (
              <button key={t.value} role="radio" aria-checked={theme === t.value} title={t.label}
                aria-label={`Tema ${t.label.toLowerCase()}`} onClick={() => setTheme(t.value)}>
                <Icon name={t.icon} size={16} />
              </button>
            ))}
          </div>
          <div className="side__user">
            <span className="avatar" aria-hidden="true">{initials || "?"}</span>
            <span className="side__who">
              <strong>{user?.name}</strong>
              <small>{user?.role === "admin" ? "Administrador" : "Usuário"}, {user?.username}</small>
            </span>
            <button className="icon-button" onClick={signOut} aria-label="Sair" title="Sair">
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <main className="stage">{children}</main>
      {palette && <CommandPalette onClose={() => setPalette(false)} onTheme={cycleTheme} />}
    </div>
  );
}
