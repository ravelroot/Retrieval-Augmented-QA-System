export type Role = "admin" | "user";

export interface User {
  username: string;
  name: string;
  role: Role;
  created_at: string;
  last_login_at: string | null;
}

export interface Session {
  token: string;
  expires_at: string;
  user: User;
}

export type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export interface DocumentItem {
  id: string;
  title: string;
  filename: string;
  size_bytes: number;
  pages: number;
  chunks: number;
  status: DocumentStatus;
  error: string | null;
  uploaded_by: string;
  created_at: string;
  indexed_at: string | null;
  can_delete: boolean;
}

export interface Source {
  rank: number;
  document_id: string | null;
  document_title: string;
  page: number;
  similarity: number | null;
  rerank_score: number | null;
  excerpt: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  answered: boolean | null;
  grounded: boolean | null;
  model: string | null;
  latency_ms: number | null;
  created_at: string;
  sources: Source[];
  my_rating: number | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  document_ids: string[];
  messages: number;
}

export interface Conversation extends ConversationSummary {
  items: Message[];
}

export interface Exchange {
  question: Message;
  answer: Message;
  conversation: ConversationSummary;
}

export interface AuthOptions {
  registration: boolean;
  default_admin: boolean;
}

export interface SystemStatus {
  version: string;
  providers: {
    llm: string;
    embedding: string;
    reranker: string;
    vector_store: string;
    collection: string;
    chunk_size: number;
    chunk_overlap: number;
    top_k: number;
    top_n: number;
    min_similarity: number;
    min_rerank_score: number;
    verify_answers: boolean;
  };
  documents: { total: number; by_status: Partial<Record<DocumentStatus, number>>; chunks: number };
  users: number | null;
  registration: boolean;
  database: string;
  integrations?: { api_keys: number; webhooks: number | null };
}

export interface SearchResult {
  query: string;
  took_ms: number;
  results: Source[];
}

export interface Metrics {
  scope: "all" | "mine";
  period_days: number;
  questions: number;
  answered: number;
  unanswered: number;
  answer_rate: number | null;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  feedback: { up: number; down: number };
  conversations: number;
  daily: { date: string; questions: number; unanswered: number }[];
  top_documents: { document_id: string | null; title: string; citations: number }[];
  unanswered_recent: { question: string; asked_at: string; conversation_id: string }[];
  negative_recent: { question: string; answer: string; asked_at: string; conversation_id: string; message_id: string }[];
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  key?: string;
}

export type WebhookEvent = "document.ready" | "document.failed" | "question.unanswered" | "feedback.negative";

export interface Webhook {
  id: string;
  url: string;
  events: WebhookEvent[];
  active: boolean;
  created_at: string;
  last_status: number | null;
  last_error: string | null;
  last_delivery_at: string | null;
  secret?: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string>;

  constructor(status: number, code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

const STORAGE_KEY = "nexo.sessao";

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (new Date(session.expires_at).getTime() <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null): void {
  try {
    if (session) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    return;
  }
}

let onUnauthorized: () => void = () => undefined;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const session = loadSession();
  const headers: Record<string, string> = {};
  if (session) headers.Authorization = `Bearer ${session.token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "NETWORK", "Não foi possível falar com o servidor do Nexo. Ele está rodando?");
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && session) onUnauthorized();
    throw new ApiError(
      response.status,
      data?.code ?? "ERROR",
      data?.message ?? `Erro ${response.status} no servidor.`,
      data?.fields ?? {},
    );
  }
  return data as T;
}

export const api = {
  options: () => request<AuthOptions>("GET", "/auth/options"),
  login: (username: string, password: string) => request<Session>("POST", "/auth/login", { username, password }),
  register: (name: string, username: string, password: string) =>
    request<Session>("POST", "/auth/register", { name, username, password }),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("PUT", "/auth/password", { current_password, new_password }),
  status: () => request<SystemStatus>("GET", "/system/status"),
  documents: () => request<DocumentItem[]>("GET", "/documents"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<DocumentItem[]>("POST", "/documents", form);
  },
  renameDocument: (id: string, title: string) => request<DocumentItem>("PATCH", `/documents/${id}`, { title }),
  reindexDocument: (id: string) => request<DocumentItem>("POST", `/documents/${id}/reindex`),
  deleteDocument: (id: string) => request<void>("DELETE", `/documents/${id}`),
  conversations: () => request<ConversationSummary[]>("GET", "/conversations"),
  conversation: (id: string) => request<Conversation>("GET", `/conversations/${id}`),
  createConversation: (document_ids: string[]) => request<Conversation>("POST", "/conversations", { document_ids }),
  updateConversation: (id: string, patch: { title?: string; document_ids?: string[] }) =>
    request<ConversationSummary>("PATCH", `/conversations/${id}`, patch),
  deleteConversation: (id: string) => request<void>("DELETE", `/conversations/${id}`),
  ask: (id: string, content: string) => request<Exchange>("POST", `/conversations/${id}/messages`, { content }),
  feedback: (id: string, rating: number) => request<Message>("POST", `/messages/${id}/feedback`, { rating }),
  search: (query: string, document_ids: string[], rerank: boolean, limit = 8) =>
    request<SearchResult>("POST", "/search", { query, document_ids, rerank, limit }),
  metrics: (days: number) => request<Metrics>("GET", `/metrics?days=${days}`),
  keys: () => request<ApiKey[]>("GET", "/keys"),
  createKey: (name: string) => request<ApiKey>("POST", "/keys", { name }),
  deleteKey: (id: string) => request<void>("DELETE", `/keys/${id}`),
  webhooks: () => request<Webhook[]>("GET", "/webhooks"),
  createWebhook: (url: string, events: WebhookEvent[], secret: string | null) =>
    request<Webhook>("POST", "/webhooks", { url, events, secret }),
  toggleWebhook: (id: string, active: boolean) => request<Webhook>("PATCH", `/webhooks/${id}`, { active }),
  deleteWebhook: (id: string) => request<void>("DELETE", `/webhooks/${id}`),
  testWebhook: (id: string) => request<{ status: number | null; error: string | null }>("POST", `/webhooks/${id}/test`),
  users: () => request<User[]>("GET", "/users"),
  setRole: (username: string, role: Role) => request<User>("PATCH", `/users/${username}`, { role }),
  deleteUser: (username: string) => request<void>("DELETE", `/users/${username}`),
};

export async function downloadExport(id: string, format: "markdown" | "json"): Promise<void> {
  const session = loadSession();
  const response = await fetch(`/api/conversations/${id}/export?format=${format}`, {
    headers: session ? { Authorization: `Bearer ${session.token}` } : {},
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.code ?? "ERROR", data?.message ?? "Não foi possível exportar a conversa.");
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const name = match?.[1] ?? `nexo-conversa.${format === "json" ? "json" : "md"}`;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function openDocument(id: string, page?: number): Promise<void> {
  const target = window.open("", "_blank");
  const session = loadSession();
  const response = await fetch(`/api/documents/${id}/file`, {
    headers: session ? { Authorization: `Bearer ${session.token}` } : {},
  });
  if (!response.ok) {
    target?.close();
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.code ?? "ERROR", data?.message ?? "Não foi possível abrir o PDF.");
  }
  const url = URL.createObjectURL(await response.blob());
  const href = page ? `${url}#page=${page}` : url;
  if (target) target.location.href = href;
  else window.location.href = href;
}
