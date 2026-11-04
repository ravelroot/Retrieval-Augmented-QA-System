export type Role = "admin" | "user";

export interface User {
  username: string;
  name: string;
  role: Role;
  created_at: string;
  last_login_at: string | null;
  tutorial_done_at: string | null;
  password_changed_at?: string | null;
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
  base_id: string;
  kind: DocumentKind;
  extension: string;
  updated_at: string | null;
  source_url?: string | null;
  outdated?: boolean;
}

export interface Chunk {
  chunk_id: string;
  index: number;
  page: number;
  text: string;
}

export interface ChunkPage {
  document_id: string;
  title: string;
  kind: DocumentKind;
  total: number;
  offset: number;
  items: Chunk[];
}

export type DocumentKind = "pdf" | "file" | "note";

export interface Source {
  rank: number;
  document_id: string | null;
  document_title: string;
  page: number;
  similarity: number | null;
  rerank_score: number | null;
  excerpt: string;
  kind?: DocumentKind;
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
  my_comment?: string | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  document_ids: string[];
  messages: number;
  bot_id: string | null;
  pinned?: boolean;
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
  documents: { total: number; by_status: Partial<Record<DocumentStatus, number>>; chunks: number; outdated?: number };
  users: number | null;
  registration: boolean;
  database: string;
  integrations?: { api_keys: number; webhooks: number | null };
  operation?: { rate_limit: number; retention_days: number; overrides: string[]; cors: string[]; log_format: string;
    token_hours: number; max_upload_mb: number };
}

export type SettingKind = "text" | "int" | "float" | "bool";

export interface SettingItem {
  name: string;
  group: string;
  label: string;
  hint: string;
  kind: SettingKind;
  value: string | number | boolean;
  default: string | number | boolean;
  overridden: boolean;
  reindex: boolean;
  min: number | null;
  max: number | null;
}

export interface SettingsData {
  items: SettingItem[];
  fixed: Record<string, string>;
  outdated: number;
  changed?: string[];
  reindex_needed?: boolean;
}

export type CheckStatus = "ok" | "warn" | "fail" | "info";

export interface Check {
  id: string;
  group: string;
  label: string;
  status: CheckStatus;
  detail: string;
  hint: string | null;
}

export interface Diagnostics {
  checked_at: string;
  deep: boolean;
  ok: number;
  warn: number;
  fail: number;
  info: number;
  checks: Check[];
}

export type MaintenanceAction = "reindex_failed" | "reindex_outdated" | "reindex_all" | "clean_orphans" | "purge_conversations" | "vacuum";

export interface AuditItem {
  id: number;
  created_at: string;
  actor: string;
  action: string;
  label: string;
  target_type: string | null;
  target_id: string | null;
  detail: string | null;
  ip: string | null;
}

export interface AuditPage {
  total: number;
  items: AuditItem[];
  actions: Record<string, string>;
}

export interface QuickReply {
  id: string;
  title: string;
  body: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  can_edit: boolean;
}

export interface BotStat {
  bot_id: string | null;
  name: string;
  color: string | null;
  questions: number;
  answered: number;
  answer_rate: number | null;
  negative: number;
  avg_latency_ms: number | null;
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
  negative_recent: { question: string; answer: string; asked_at: string; conversation_id: string; message_id: string;
    comment: string | null; owner: string | null }[];
  by_bot: BotStat[];
  bot_id: string | null;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  key?: string;
  scope: KeyScope;
  expires_at: string | null;
  expired: boolean;
}

export type KeyScope = "full" | "ask" | "feed";

export type WebhookEvent = "document.ready" | "document.failed" | "question.unanswered" | "feedback.negative"
  | "whatsapp.message" | "whatsapp.handoff";

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

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  color: string;
  is_default: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  documents: number;
  ready: number;
  processing: number;
  failed: number;
  notes: number;
  files: number;
  pages: number;
  chunks: number;
  bots: number;
  can_edit: boolean;
}

export interface BaseInput {
  name?: string;
  description?: string | null;
  color?: string;
}

export interface Bot {
  id: string;
  name: string;
  description: string | null;
  base_id: string;
  base_name: string;
  instructions: string | null;
  greeting: string | null;
  fallback: string | null;
  color: string;
  cite_sources: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  conversations: number;
  ready: boolean;
  can_edit: boolean;
  suggestions: string[];
}

export interface BotInput {
  name?: string;
  base_id?: string;
  description?: string | null;
  instructions?: string | null;
  greeting?: string | null;
  fallback?: string | null;
  color?: string;
  cite_sources?: boolean;
  suggestions?: string[];
}

export type Provider = "cloud" | "evolution" | "simulador";

export interface Channel {
  id: string;
  name: string;
  provider: Provider;
  bot_id: string | null;
  bot_name: string | null;
  auto_reply: boolean;
  active: boolean;
  phone: string | null;
  webhook_path: string;
  verify_token: string;
  settings: { api_version: string | null; phone_number_id: string | null; base_url: string | null; instance: string | null };
  secrets: { access_token: string | null; app_secret: string | null; api_key: string | null };
  created_at: string;
  last_event_at: string | null;
  last_error: string | null;
  contacts: number;
  unread: number;
  waiting: number;
}

export interface ChannelInput {
  name?: string;
  provider?: Provider;
  bot_id?: string | null;
  auto_reply?: boolean;
  active?: boolean;
  phone?: string | null;
  api_version?: string | null;
  phone_number_id?: string | null;
  access_token?: string | null;
  app_secret?: string | null;
  base_url?: string | null;
  api_key?: string | null;
  instance?: string | null;
}

export interface ChannelStatus {
  state: "open" | "connecting" | "close" | "unknown";
  detail: string | null;
}

export interface Contact {
  id: string;
  channel_id: string;
  phone: string;
  name: string | null;
  bot_enabled: boolean;
  needs_human: boolean;
  unread: number;
  last_message: string | null;
  last_direction: "in" | "out" | null;
  last_message_at: string | null;
  created_at: string;
}

export interface WaMessage {
  id: string;
  direction: "in" | "out";
  author: string;
  body: string;
  status: "received" | "pending" | "sent" | "delivered" | "read" | "failed";
  error: string | null;
  created_at: string;
  answered: boolean | null;
  sources: Source[];
}

export interface ContactDetail extends Contact {
  messages: WaMessage[];
}

export interface WaSummary {
  channels: number;
  contacts: number;
  unread: number;
  waiting: number;
  bot_answers_today: number;
}

export type ContactFilter = "all" | "unread" | "waiting" | "bot" | "human";

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

function failure(status: number, data: { code?: string; message?: string; fields?: Record<string, string> } | null,
  fallback: string): ApiError {
  return new ApiError(status, data?.code ?? "ERROR", data?.message ?? fallback, data?.fields ?? {});
}

export type StreamStage = "searching" | "writing";

export interface StreamHandlers {
  onStage?: (stage: StreamStage) => void;
  onDelta?: (text: string) => void;
  signal?: AbortSignal;
}

export async function askStream(id: string, content: string, handlers: StreamHandlers = {}): Promise<Exchange> {
  const session = loadSession();
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "text/event-stream" };
  if (session) headers.Authorization = `Bearer ${session.token}`;
  let response: Response;
  try {
    response = await fetch(`/api/conversations/${id}/messages/stream`, {
      method: "POST", headers, body: JSON.stringify({ content }), signal: handlers.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new ApiError(0, "ABORTED", "Resposta interrompida.");
    throw new ApiError(0, "NETWORK", "Não foi possível falar com o servidor do Nexo. Ele está rodando?");
  }
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => null);
    if (response.status === 401 && session) onUnauthorized();
    throw failure(response.status, data, `Erro ${response.status} no servidor.`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let cut = buffer.indexOf("\n\n");
      while (cut >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        cut = buffer.indexOf("\n\n");
        let event = "message";
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const payload = JSON.parse(data);
        if (event === "status") handlers.onStage?.(payload.stage as StreamStage);
        else if (event === "delta") handlers.onDelta?.(payload.text as string);
        else if (event === "done") return payload as Exchange;
        else if (event === "error") throw failure(502, payload, "O modelo não respondeu.");
      }
      if (done) break;
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError(0, "ABORTED", "Resposta interrompida.");
    throw new ApiError(0, "NETWORK", "A conexão caiu antes do fim da resposta. Tente de novo.");
  } finally {
    reader.releaseLock();
  }
  throw new ApiError(0, "NETWORK", "A conexão caiu antes do fim da resposta. Tente de novo.");
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
    request<Session>("PUT", "/auth/password", { current_password, new_password }),
  revokeSessions: () => request<Session>("POST", "/auth/sessions/revoke"),
  updateMe: (name: string) => request<User>("PATCH", "/auth/me", { name }),
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
  updateConversation: (id: string, patch: { title?: string; document_ids?: string[]; pinned?: boolean }) =>
    request<ConversationSummary>("PATCH", `/conversations/${id}`, patch),
  deleteConversation: (id: string) => request<void>("DELETE", `/conversations/${id}`),
  ask: (id: string, content: string) => request<Exchange>("POST", `/conversations/${id}/messages`, { content }),
  regenerate: (id: string) => request<Message>("POST", `/messages/${id}/regenerate`),
  searchConversations: (q: string, only: "general" | "bots" = "general") =>
    request<ConversationSummary[]>("GET", `/conversations?only=${only}&q=${encodeURIComponent(q)}`),
  bulkDocuments: (action: "reindex" | "delete" | "move", ids: string[], base_id?: string) =>
    request<{ done: string[]; skipped: Record<string, string> }>("POST", "/documents/bulk", { action, ids, base_id }),
  feedback: (id: string, rating: number, comment?: string | null) =>
    request<Message>("POST", `/messages/${id}/feedback`, { rating, comment: comment ?? null }),
  search: (query: string, document_ids: string[], rerank: boolean, limit = 8) =>
    request<SearchResult>("POST", "/search", { query, document_ids, rerank, limit }),
  metrics: (days: number, bot_id = "") =>
    request<Metrics>("GET", `/metrics?days=${days}${bot_id ? `&bot_id=${encodeURIComponent(bot_id)}` : ""}`),
  keys: () => request<ApiKey[]>("GET", "/keys"),
  createKey: (name: string, scope: KeyScope = "full", expires_days: number | null = null) =>
    request<ApiKey>("POST", "/keys", { name, scope, expires_days }),
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
  createUser: (input: { name: string; username: string; password: string; role: Role }) =>
    request<User>("POST", "/users", input),
  resetPassword: (username: string, password: string) =>
    request<User>("PUT", `/users/${username}/password`, { password }),
  tutorial: (done: boolean) => request<User>("PUT", "/auth/tutorial", { done }),
  formats: () => request<{ extensions: string[]; max_upload_mb: number }>("GET", "/formats"),
  bases: () => request<KnowledgeBase[]>("GET", "/bases"),
  base: (id: string) => request<KnowledgeBase>("GET", `/bases/${id}`),
  createBase: (input: BaseInput) => request<KnowledgeBase>("POST", "/bases", input),
  updateBase: (id: string, input: BaseInput) => request<KnowledgeBase>("PATCH", `/bases/${id}`, input),
  deleteBase: (id: string) => request<void>("DELETE", `/bases/${id}`),
  baseDocuments: (id: string) => request<DocumentItem[]>("GET", `/bases/${id}/documents`),
  uploadToBase: (id: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<DocumentItem[]>("POST", `/bases/${id}/documents`, form);
  },
  createText: (id: string, title: string, content: string) =>
    request<DocumentItem>("POST", `/bases/${id}/texts`, { title, content }),
  documentText: (id: string) => request<{ title: string; content: string }>("GET", `/documents/${id}/text`),
  updateText: (id: string, title: string, content: string) =>
    request<DocumentItem>("PUT", `/documents/${id}/text`, { title, content }),
  moveDocument: (id: string, base_id: string) => request<DocumentItem>("PATCH", `/documents/${id}`, { base_id }),
  searchBase: (query: string, base_id: string, rerank: boolean, limit = 8) =>
    request<SearchResult>("POST", "/search", { query, base_id, rerank, limit }),
  bots: () => request<Bot[]>("GET", "/bots"),
  bot: (id: string) => request<Bot>("GET", `/bots/${id}`),
  createBot: (input: BotInput) => request<Bot>("POST", "/bots", input),
  updateBot: (id: string, input: BotInput) => request<Bot>("PATCH", `/bots/${id}`, input),
  deleteBot: (id: string) => request<void>("DELETE", `/bots/${id}`),
  botConversations: (bot_id?: string) =>
    request<ConversationSummary[]>("GET", bot_id ? `/conversations?bot_id=${bot_id}` : "/conversations?only=bots"),
  generalConversations: () => request<ConversationSummary[]>("GET", "/conversations?only=general"),
  createBotConversation: (bot_id: string) => request<Conversation>("POST", "/conversations", { bot_id }),
  channels: () => request<Channel[]>("GET", "/whatsapp/channels"),
  createChannel: (input: ChannelInput) => request<Channel>("POST", "/whatsapp/channels", input),
  updateChannel: (id: string, input: ChannelInput) => request<Channel>("PATCH", `/whatsapp/channels/${id}`, input),
  deleteChannel: (id: string) => request<void>("DELETE", `/whatsapp/channels/${id}`),
  channelStatus: (id: string) => request<ChannelStatus>("GET", `/whatsapp/channels/${id}/status`),
  channelQr: (id: string) =>
    request<{ state: ChannelStatus["state"]; base64: string | null; pairing_code: string | null }>("GET", `/whatsapp/channels/${id}/qrcode`),
  channelWebhook: (id: string, public_url: string) =>
    request<{ ok: boolean; url: string; detail: string | null }>("POST", `/whatsapp/channels/${id}/webhook`, { public_url }),
  simulate: (id: string, phone: string, name: string, text: string) =>
    request<{ contact_id: string }>("POST", `/whatsapp/channels/${id}/simulate`, { phone, name, text }),
  waSummary: () => request<WaSummary>("GET", "/whatsapp/summary"),
  contacts: (channel_id: string, filter: ContactFilter, q: string) =>
    request<Contact[]>("GET", `/whatsapp/contacts?channel_id=${encodeURIComponent(channel_id)}&filter=${filter}&q=${encodeURIComponent(q)}`),
  contact: (id: string) => request<ContactDetail>("GET", `/whatsapp/contacts/${id}`),
  sendToContact: (id: string, text: string) => request<WaMessage>("POST", `/whatsapp/contacts/${id}/messages`, { text }),
  updateContact: (id: string, patch: { bot_enabled?: boolean; needs_human?: boolean; name?: string }) =>
    request<Contact>("PATCH", `/whatsapp/contacts/${id}`, patch),
  suggest: (id: string) => request<{ text: string; answered: boolean; sources: Source[] }>("POST", `/whatsapp/contacts/${id}/suggest`),
  duplicateBot: (id: string) => request<Bot>("POST", `/bots/${id}/duplicate`),
  createSample: () => request<{ base: KnowledgeBase; bot: Bot; added: number; existed: boolean }>("POST", "/bases/sample"),
  importLink: (base_id: string, url: string, title?: string) =>
    request<DocumentItem>("POST", `/bases/${base_id}/links`, { url, title: title || null }),
  refetch: (id: string) => request<{ document: DocumentItem; changed: boolean }>("POST", `/documents/${id}/refetch`),
  chunks: (id: string, offset = 0, limit = 50, q = "") =>
    request<ChunkPage>("GET", `/documents/${id}/chunks?offset=${offset}&limit=${limit}&q=${encodeURIComponent(q)}`),
  settings: () => request<SettingsData>("GET", "/system/settings"),
  saveSettings: (values: Record<string, string | number | boolean>) => request<SettingsData>("PUT", "/system/settings", { values }),
  resetSettings: (names?: string[]) => request<SettingsData>("POST", "/system/settings/reset", { names: names ?? null }),
  diagnostics: (deep = false) => request<Diagnostics>("GET", `/system/diagnostics${deep ? "?deep=true" : ""}`),
  maintenance: (action: MaintenanceAction, days?: number) =>
    request<{ action: string; message: string; count: number; skipped: number }>("POST", "/system/maintenance", { action, days: days ?? null }),
  audit: (params: { actor?: string; action?: string; days?: number; offset?: number; limit?: number }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== 0) query.set(k, String(v)); });
    return request<AuditPage>("GET", `/audit?${query.toString()}`);
  },
  quickReplies: () => request<QuickReply[]>("GET", "/whatsapp/quick-replies"),
  createQuickReply: (title: string, body: string) => request<QuickReply>("POST", "/whatsapp/quick-replies", { title, body }),
  updateQuickReply: (id: string, patch: { title?: string; body?: string }) =>
    request<QuickReply>("PATCH", `/whatsapp/quick-replies/${id}`, patch),
  deleteQuickReply: (id: string) => request<void>("DELETE", `/whatsapp/quick-replies/${id}`),
  health: () => request<{ status: string; version: string }>("GET", "/health"),
};

async function download(path: string, fallbackName: string, fallbackError: string): Promise<void> {
  const session = loadSession();
  const response = await fetch(`/api${path}`, {
    headers: session ? { Authorization: `Bearer ${session.token}` } : {},
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (response.status === 401 && session) onUnauthorized();
    throw failure(response.status, data, fallbackError);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const name = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadExport(id: string, format: "markdown" | "json"): Promise<void> {
  return download(`/conversations/${id}/export?format=${format}`, `nexo-conversa.${format === "json" ? "json" : "md"}`,
    "Não foi possível exportar a conversa.");
}

export function downloadMetrics(days: number, bot_id = ""): Promise<void> {
  return download(`/metrics/export?days=${days}${bot_id ? `&bot_id=${encodeURIComponent(bot_id)}` : ""}`,
    `nexo-perguntas-${days}d.csv`, "Não foi possível exportar as perguntas.");
}

export function downloadBackup(): Promise<void> {
  return download("/system/backup", "nexo-backup.zip", "Não foi possível gerar o backup.");
}

export function downloadAudit(params: { actor?: string; action?: string; days?: number }): Promise<void> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== 0) query.set(k, String(v)); });
  return download(`/audit/export?${query.toString()}`, "nexo-atividades.csv", "Não foi possível exportar as atividades.");
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
