import { useEffect, useState } from "react";

export interface BridgeResult {
  ok: boolean;
  status?: number;
  code?: string;
  message?: string;
  cancelado?: boolean;
}

interface Bridge {
  abrir_documento(id: string, pagina: number | null, token: string): Promise<BridgeResult>;
  abrir_pagina(caminho: string): Promise<BridgeResult>;
  restaurar_backup(token: string): Promise<BridgeResult>;
  definir_tema(tema: "light" | "dark"): Promise<BridgeResult>;
}

declare global {
  interface Window {
    pywebview?: { api?: Partial<Bridge> };
  }
}

function ready(): Bridge | null {
  const api = window.pywebview?.api;
  return api && typeof api.abrir_documento === "function" ? (api as Bridge) : null;
}

export function useInApp(): boolean {
  const [value, setValue] = useState(() => ready() !== null);
  useEffect(() => {
    if (value) return;
    const update = () => setValue(ready() !== null);
    window.addEventListener("pywebviewready", update);
    update();
    return () => window.removeEventListener("pywebviewready", update);
  }, [value]);
  return value;
}

export function bridge(timeout = 3000): Promise<Bridge | null> {
  const found = ready();
  if (found || window.pywebview === undefined) return Promise.resolve(found);
  return new Promise((resolve) => {
    const done = () => {
      window.clearTimeout(timer);
      window.removeEventListener("pywebviewready", done);
      resolve(ready());
    };
    const timer = window.setTimeout(done, timeout);
    window.addEventListener("pywebviewready", done);
  });
}

export function installLinkHandler(): void {
  document.addEventListener("click", (event) => {
    const link = (event.target as Element | null)?.closest?.("a[target='_blank']") as HTMLAnchorElement | null;
    if (!link || !link.href) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || !ready()) return;
    event.preventDefault();
    void bridge().then((api) => api?.abrir_pagina(url.pathname));
  }, true);
}

export function syncWindowTheme(theme: "light" | "dark"): void {
  const api = ready();
  if (api) void api.definir_tema(theme).catch(() => undefined);
}
