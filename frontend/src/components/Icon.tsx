const paths: Record<string, string> = {
  chat: "M4 5h16v11H9l-5 4z",
  docs: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  system: "M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M11 16v4",
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
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  scope: "M3 17h18M8 17v-4M16 17v-4M5 9h6v4H5zM13 9h6v4h-6z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof paths | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name] ?? ""} />
    </svg>
  );
}
