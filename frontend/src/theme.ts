import { useEffect, useState } from "react";
import { syncWindowTheme } from "./desktop";

export type ThemeChoice = "light" | "dark" | "auto";

const KEY = "nexo.tema";
const media = () => window.matchMedia?.("(prefers-color-scheme: dark)");

export function initialTheme(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark" || saved === "auto") return saved;
  } catch {
    return "auto";
  }
  return "auto";
}

export function resolveTheme(choice: ThemeChoice): "light" | "dark" {
  if (choice !== "auto") return choice;
  return media()?.matches ? "dark" : "light";
}

export function toggleTheme(choice: ThemeChoice): ThemeChoice {
  return resolveTheme(choice) === "dark" ? "light" : "dark";
}

export function applyTheme(choice: ThemeChoice): void {
  const resolved = resolveTheme(choice);
  document.documentElement.dataset.theme = resolved;
  syncWindowTheme(resolved);
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    return;
  }
}

export function watchSystemTheme(onChange: () => void): () => void {
  const query = media();
  if (!query) return () => undefined;
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export function useTheme(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const [theme, setTheme] = useState<ThemeChoice>(initialTheme);
  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => (theme === "auto" ? watchSystemTheme(() => applyTheme("auto")) : undefined), [theme]);
  return [theme, setTheme];
}
