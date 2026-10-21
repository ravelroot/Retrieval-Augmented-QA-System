const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const dayMonth = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });
const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });

function parse(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function formatDateTime(value: string | null): string {
  return value ? dateTime.format(parse(value)) : "";
}

export function formatRelative(value: string): string {
  const date = parse(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return time.format(date);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "ontem";
  return dayMonth.format(date).replace(".", "");
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

export function formatScore(value: number | null): string {
  return value === null ? "não calculado" : value.toFixed(2).replace(".", ",");
}

export function plural(count: number, one: string, many: string): string {
  return `${count.toLocaleString("pt-BR")} ${count === 1 ? one : many}`;
}
