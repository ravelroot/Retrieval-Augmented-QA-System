import type { DocumentStatus } from "../api";

const labels: Record<DocumentStatus, string> = {
  PENDING: "Na fila",
  PROCESSING: "Indexando",
  READY: "Pronto",
  FAILED: "Falhou",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`badge badge--${status.toLowerCase()}`}>{labels[status]}</span>;
}
