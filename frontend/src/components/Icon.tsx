const paths: Record<string, string> = {
  chat: "M4 5h16v11H9l-5 4z",
  docs: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  system: "M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M11 16v4",
  search: "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM15.5 15.5 20 20",
  chart: "M4 20h16M7 16v-5M12 16V7M17 16v-8",
  plug: "M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4",
  plus: "M12 5v14M5 12h14",
  send: "M5 12h13M13 6l6 6-6 6",
  trash: "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13",
  up: "M7 11l5-5 5 5M12 6v13",
  down: "M7 13l5 5 5-5M12 18V5",
  close: "M6 6l12 12M18 6L6 18",
  menu: "M4 7h16M4 12h16M4 17h16",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  open: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6",
  edit: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
  sun: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  auto: "M12 3a9 9 0 1 0 0 18zM12 3a9 9 0 0 1 0 18",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  check: "M5 12l5 5 9-10",
  download: "M12 4v12M7 11l5 5 5-5M5 20h14",
  key: "M14 10a4 4 0 1 0-3.5 4L9 15.5V18H6.5v2.5H4V18l6.3-6.3M15 8h.01",
  hook: "M8 9a4 4 0 1 1 6 3.5L12 14v3M12 21h.01M6 17a3 3 0 1 0 3 3",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  command: "M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z",
  filter: "M4 5h16l-6 8v6l-4-2v-4z",
  bolt: "M13 3 5 14h6l-1 7 8-11h-6z",
  pause: "M8 5v14M16 5v14",
  play: "M7 5l12 7-12 7z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof paths | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name] ?? ""} />
    </svg>
  );
}
