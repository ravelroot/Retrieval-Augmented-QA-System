import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { applyTheme, initialTheme, type Theme } from "../theme";
import { Icon } from "./Icon";
import { Wordmark } from "./Logo";

const links = [
  { to: "/conversas", label: "Conversas", icon: "chat" },
  { to: "/documentos", label: "Documentos", icon: "docs" },
  { to: "/sistema", label: "Sistema e conta", icon: "system" },
];

export function Shell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className={`shell${open ? " shell--open" : ""}`}>
      <header className="topbar">
        <button className="icon-button" onClick={() => setOpen(true)} aria-label="Abrir menu">
          <Icon name="menu" />
        </button>
        <Wordmark size={30} />
      </header>
      <aside className="rail" aria-label="Navegação principal">
        <div className="rail__head">
          <Wordmark />
          <button className="icon-button rail__close" onClick={() => setOpen(false)} aria-label="Fechar menu">
            <Icon name="close" />
          </button>
        </div>
        <nav className="rail__nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className="rail__link">
              <Icon name={link.icon} />
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rail__foot">
          <div className="rail__user">
            <span className="avatar" aria-hidden="true">{user?.name.slice(0, 1).toUpperCase()}</span>
            <span>
              <strong>{user?.name}</strong>
              <small>{user?.role === "admin" ? "Administrador" : "Usuário"} ({user?.username})</small>
            </span>
          </div>
          <div className="rail__actions">
            <button className="ghost-button" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
              <Icon name={theme === "light" ? "moon" : "sun"} />
              {theme === "light" ? "Tema escuro" : "Tema claro"}
            </button>
            <button className="ghost-button" onClick={signOut}>
              <Icon name="logout" />
              Sair
            </button>
          </div>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <main className="stage">{children}</main>
    </div>
  );
}
