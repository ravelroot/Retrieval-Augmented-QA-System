import { resolveTheme, toggleTheme, type ThemeChoice } from "../theme";
import { Icon } from "./Icon";

export function ThemeSwitch({ theme, onChange, className = "theme-switch" }: {
  theme: ThemeChoice; onChange: (choice: ThemeChoice) => void; className?: string;
}) {
  const dark = resolveTheme(theme) === "dark";
  const label = dark ? "Tema claro" : "Tema escuro";
  return (
    <button type="button" className={className} onClick={() => onChange(toggleTheme(theme))}
      title={dark ? "Mudar para o tema claro" : "Mudar para o tema escuro"} aria-label={dark ? "Mudar para o tema claro" : "Mudar para o tema escuro"}>
      <Icon name={dark ? "sun" : "moon"} />
      <span>{label}</span>
    </button>
  );
}
