import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { applyTheme, initialTheme, type Theme } from "../theme";
import { Icon } from "./Icon";
import { Brand } from "./Logo";

const groups = [
  {
    title: "Consulta",
    links: [
      { to: "/conversas", label: "Conversas", icon: "chat" },
      { to: "/documentos", label: "Documentos", icon: "docs" },
    ],
  },
  {
    title: "Conta",
    links: [{ to: "/sistema", label: "Sistema e conta", icon: "system" }],
  },
];

export function Shell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => setOpen(false), [location.pathname]);

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
      </header>
      <aside className="rail" aria-label="Navegação principal">
        <div className="rail__head">
          <Brand />
          <button className="icon-button rail__close" onClick={() => setOpen(false)} aria-label="Fechar menu">
            <Icon name="close" />
          </button>
        </div>
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
            <button className="rail__link" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
              <Icon name={theme === "light" ? "moon" : "sun"} />
              <span>{theme === "light" ? "Tema escuro" : "Tema claro"}</span>
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
    </div>
  );
}
