import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api, openDocument, type Bot, type DocumentItem, type KnowledgeBase, type SearchResult } from "../api";
import { Icon } from "../components/Icon";
import { SourceSlip } from "../components/SourceSlip";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { formatDateTime, formatSize, plural } from "../format";
import { kindLabel, unitLabel } from "./Documents";

type Tab = "arquivos" | "textos" | "testar" | "integrar";
type Lang = "curl" | "python" | "javascript";

const TABS: { id: Tab; label: string }[] = [
  { id: "arquivos", label: "Arquivos" },
  { id: "textos", label: "Textos" },
  { id: "testar", label: "Testar" },
  { id: "integrar", label: "Integrar" },
];

const COLORS = ["#000000", "#4d4b4b", "#2b4c5a", "#3e6b2a", "#7a5a12", "#9b2f1e", "#5a3e6b", "#bab7b6"];
const ALLOWED = [".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".html", ".htm"];

function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function CopyButton({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="ghost-button small" onClick={() => {
      navigator.clipboard.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); }).catch(() => undefined);
    }}>
      <Icon name={done ? "check" : "copy"} size={15} />
      {done ? "Copiado" : label}
    </button>
  );
}

function BaseForm({ initial, onDone, onCancel }: { initial?: KnowledgeBase; onDone: (b: KnowledgeBase) => void; onCancel: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [color, setColor] = useState(initial?.color ?? COLORS[0]);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const input = { name: name.trim(), description: description.trim() || null, color };
      onDone(initial ? await api.updateBase(initial.id, input) : await api.createBase(input));
    } catch (err) {
      toast((err as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="kb-form" onSubmit={submit}>
      <label className="kb-field">
        <span>Nome</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus placeholder="Ex.: Suporte técnico" />
      </label>
      <label className="kb-field">
        <span>Descrição</span>
        <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} placeholder="O que esta base guarda" />
      </label>
      <div className="kb-colors" role="radiogroup" aria-label="Cor">
        {COLORS.map((c) => (
          <button key={c} type="button" role="radio" aria-checked={color === c} aria-label={`Cor ${c}`}
            className={`kb-swatch${color === c ? " is-on" : ""}`} style={{ background: c }} onClick={() => setColor(c)} />
        ))}
      </div>
      <div className="kb-form__actions">
        <button className="primary-button small" type="submit" disabled={!name.trim() || busy}>{initial ? "Salvar" : "Criar base"}</button>
        <button className="ghost-button small" type="button" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}

function FilesTab({ base, bases, docs, reload, onNotice }: {
  base: KnowledgeBase; bases: KnowledgeBase[]; docs: DocumentItem[]; reload: () => void; onNotice: (kind: "ok" | "error", text: string) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const [formats, setFormats] = useState<{ extensions: string[]; max_upload_mb: number } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { api.formats().then(setFormats).catch(() => undefined); }, []);

  const files = useMemo(() => {
    const q = fold(filter.trim());
    return docs.filter((d) => d.kind !== "note" && (!q || fold(`${d.title} ${d.filename}`).includes(q)));
  }, [docs, filter]);

  async function send(list: FileList | File[]) {
    const chosen = Array.from(list).filter((f) => ALLOWED.some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (!chosen.length) {
      onNotice("error", "Escolha arquivos PDF, Word, TXT, Markdown, CSV, JSON ou HTML.");
      return;
    }
    setUploading(true);
    try {
      const created = await api.uploadToBase(base.id, chosen);
      onNotice("ok", `${plural(created.length, "arquivo enviado", "arquivos enviados")} para ${base.name}. A indexação começa em seguida.`);
      reload();
    } catch (e) {
      onNotice("error", (e as ApiError).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  async function act(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      onNotice("ok", done);
      reload();
    } catch (e) {
      onNotice("error", (e as ApiError).message);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) void send(e.dataTransfer.files);
  }

  const exts = formats?.extensions.map((x) => x.replace(/^\./, "").toUpperCase()).join(", ") ?? "PDF, DOCX, TXT, MD, CSV, JSON, HTML";

  return (
    <div className="kb-tab">
      <div className={`kb-drop${dragging ? " kb-drop--active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
        <span className="dropzone__icon"><Icon name="upload" size={22} /></span>
        <div>
          <strong>{uploading ? "Enviando…" : "Arraste arquivos para esta base"}</strong>
          <p>Aceita {exts}{formats ? `, até ${formats.max_upload_mb} MB cada` : ""}. O conteúdo vira trechos que o agente consulta.</p>
        </div>
        <button className="primary-button" onClick={() => input.current?.click()} disabled={uploading}>
          <Icon name="plus" size={16} />Escolher arquivos
        </button>
        <input ref={input} type="file" multiple hidden accept={ALLOWED.join(",")}
          onChange={(e) => e.target.files && send(e.target.files)} />
      </div>

      {docs.some((d) => d.kind !== "note") && (
        <input className="toolbar__search kb-filter" value={filter} onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar arquivos pelo nome" aria-label="Filtrar arquivos" />
      )}

      {files.length > 0 && (
        <ul className="kb-items">
          {files.map((doc) => (
            <li key={doc.id} className="kb-item">
              <span className="kb-ext" aria-hidden="true">{kindLabel(doc)}</span>
              <div className="kb-item__main">
                <strong>{doc.title}</strong>
                <span className="kb-item__meta">
                  <span>{doc.filename}</span>
                  <span>{formatSize(doc.size_bytes)}</span>
                  {doc.status === "READY" && <span>{unitLabel(doc, doc.pages)}</span>}
                  {doc.status === "READY" && <span>{plural(doc.chunks, "trecho", "trechos")}</span>}
                  <span>{formatDateTime(doc.created_at)}</span>
                </span>
                {doc.status === "FAILED" && doc.error && <span className="doc__error">{doc.error}</span>}
                {(doc.status === "PENDING" || doc.status === "PROCESSING") && <div className="busline" aria-hidden="true"><span /></div>}
              </div>
              <StatusBadge status={doc.status} />
              <div className="kb-item__actions">
                {confirming === doc.id ? (
                  <>
                    <span className="doc__confirm">Excluir arquivo e trechos?</span>
                    <button className="danger-button small" onClick={() => { setConfirming(null); void act(() => api.deleteDocument(doc.id), "Arquivo excluído da base."); }}>Excluir</button>
                    <button className="ghost-button small" onClick={() => setConfirming(null)}>Manter</button>
                  </>
                ) : moving === doc.id ? (
                  <label className="select kb-move">
                    <span>Mover para</span>
                    <select autoFocus defaultValue="" onChange={(e) => {
                      const to = e.target.value;
                      setMoving(null);
                      if (to) void act(() => api.moveDocument(doc.id, to), `Movido para ${bases.find((b) => b.id === to)?.name ?? "outra base"}.`);
                    }} onBlur={() => setMoving(null)}>
                      <option value="">Escolha a base</option>
                      {bases.filter((b) => b.id !== base.id).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                    </select>
                  </label>
                ) : (
                  <>
                    {doc.kind === "pdf" && (
                      <button className="icon-button" title="Abrir PDF" aria-label={`Abrir ${doc.title}`}
                        onClick={() => openDocument(doc.id).catch((e: ApiError) => onNotice("error", e.message))}>
                        <Icon name="open" />
                      </button>
                    )}
                    {doc.can_delete && (
                      <>
                        {bases.length > 1 && (
                          <button className="icon-button" title="Mover para outra base" aria-label={`Mover ${doc.title}`} onClick={() => setMoving(doc.id)}>
                            <Icon name="move" />
                          </button>
                        )}
                        <button className="icon-button" title="Reindexar" aria-label={`Reindexar ${doc.title}`}
                          disabled={doc.status === "PENDING" || doc.status === "PROCESSING"}
                          onClick={() => act(() => api.reindexDocument(doc.id), "Reindexação iniciada.")}>
                          <Icon name="refresh" />
                        </button>
                        <button className="icon-button" title="Excluir" aria-label={`Excluir ${doc.title}`} onClick={() => setConfirming(doc.id)}>
                          <Icon name="trash" />
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {docs.some((d) => d.kind !== "note") && files.length === 0 && <p className="toolbar__empty">Nenhum arquivo com “{filter}”.</p>}
    </div>
  );
}

function TextsTab({ base, docs, reload, onNotice }: {
  base: KnowledgeBase; docs: DocumentItem[]; reload: () => void; onNotice: (kind: "ok" | "error", text: string) => void;
}) {
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const notes = docs.filter((d) => d.kind === "note");

  useEffect(() => {
    notes.filter((n) => previews[n.id] === undefined).forEach((n) => {
      api.documentText(n.id).then((t) => setPreviews((p) => ({ ...p, [n.id]: t.content }))).catch(() => undefined);
    });
  }, [notes.map((n) => `${n.id}:${n.updated_at ?? ""}`).join("|")]);

  async function open(doc: DocumentItem) {
    try {
      const t = await api.documentText(doc.id);
      setTitle(t.title);
      setContent(t.content);
      setEditing(doc.id);
    } catch (e) {
      onNotice("error", (e as ApiError).message);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    try {
      if (editing === "new") await api.createText(base.id, title.trim(), content.trim());
      else if (editing) await api.updateText(editing, title.trim(), content.trim());
      onNotice("ok", editing === "new" ? "Texto adicionado. Em instantes ele entra nas respostas." : "Texto atualizado e reindexado.");
      if (editing && editing !== "new") setPreviews((p) => ({ ...p, [editing]: content.trim() }));
      setEditing(null);
      setTitle("");
      setContent("");
      reload();
    } catch (err) {
      onNotice("error", (err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteDocument(id);
      setConfirming(null);
      onNotice("ok", "Texto excluído da base.");
      reload();
    } catch (err) {
      onNotice("error", (err as ApiError).message);
    }
  }

  return (
    <div className="kb-tab">
      {editing ? (
        <form className="kb-editor" onSubmit={save}>
          <label className="kb-field">
            <span>Título</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} autoFocus
              placeholder="Ex.: Horário de atendimento" />
          </label>
          <label className="kb-field">
            <span>Conteúdo</span>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={12} maxLength={200000}
              placeholder="Escreva a informação como você explicaria a um cliente. Ex.: Atendemos de segunda a sexta, das 8h às 18h. Aos sábados, das 9h às 13h." />
          </label>
          <div className="kb-form__actions">
            <button className="primary-button" type="submit" disabled={busy || !title.trim() || !content.trim()}>
              <Icon name="check" size={16} />{editing === "new" ? "Adicionar à base" : "Salvar alterações"}
            </button>
            <button className="ghost-button" type="button" onClick={() => setEditing(null)}>Cancelar</button>
            <span className="kb-hint">{content.length.toLocaleString("pt-BR")} caracteres</span>
          </div>
        </form>
      ) : (
        <div className="kb-newtext">
          <div>
            <strong>Adicione uma informação agora</strong>
            <p>Preços, horários, políticas, respostas prontas. O texto entra na base e o agente passa a usá-lo em segundos.</p>
          </div>
          <button className="primary-button" onClick={() => { setTitle(""); setContent(""); setEditing("new"); }}>
            <Icon name="plus" size={16} />Novo texto
          </button>
        </div>
      )}

      {notes.length > 0 && (
        <ul className="kb-items">
          {notes.map((doc) => (
            <li key={doc.id} className="kb-item">
              <span className="kb-ext" aria-hidden="true"><Icon name="text" size={16} /></span>
              <div className="kb-item__main">
                <strong>{doc.title}</strong>
                {previews[doc.id] && <span className="kb-preview">{previews[doc.id]}</span>}
                <span className="kb-item__meta">
                  <span>{doc.updated_at ? `Editado em ${formatDateTime(doc.updated_at)}` : `Criado em ${formatDateTime(doc.created_at)}`}</span>
                  {doc.status === "READY" && <span>{plural(doc.chunks, "trecho", "trechos")}</span>}
                  <span>por {doc.uploaded_by}</span>
                </span>
              </div>
              <StatusBadge status={doc.status} />
              <div className="kb-item__actions">
                {confirming === doc.id ? (
                  <>
                    <span className="doc__confirm">Excluir este texto?</span>
                    <button className="danger-button small" onClick={() => remove(doc.id)}>Excluir</button>
                    <button className="ghost-button small" onClick={() => setConfirming(null)}>Manter</button>
                  </>
                ) : doc.can_delete && (
                  <>
                    <button className="icon-button" title="Editar" aria-label={`Editar ${doc.title}`} onClick={() => open(doc)}>
                      <Icon name="edit" />
                    </button>
                    <button className="icon-button" title="Excluir" aria-label={`Excluir ${doc.title}`} onClick={() => setConfirming(doc.id)}>
                      <Icon name="trash" />
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TestTab({ base }: { base: KnowledgeBase }) {
  const [query, setQuery] = useState("");
  const [rerank, setRerank] = useState(true);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError("");
    try {
      setResult(await api.searchBase(query.trim(), base.id, rerank));
    } catch (err) {
      setError((err as ApiError).message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kb-tab">
      <p className="panel__lead">Veja o que o agente encontraria nesta base para uma pergunta, sem gerar resposta. Útil para conferir se uma informação já está lá.</p>
      <form className="kb-search" onSubmit={run}>
        <Icon name="search" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Pergunte algo sobre ${base.name}`} aria-label="Busca na base" />
        <label className="check check--inline">
          <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />Reranking
        </label>
        <button className="primary-button small" type="submit" disabled={busy || !query.trim()}>{busy ? "Buscando…" : "Buscar"}</button>
      </form>
      {error && <p className="alert" role="alert">{error}</p>}
      {result && (
        <div className="kb-results">
          <p className="kb-hint">{plural(result.results.length, "trecho encontrado", "trechos encontrados")} em {result.took_ms} ms.</p>
          {result.results.length === 0 ? (
            <p className="panel__lead">Nada relevante nesta base. Adicione um texto ou arquivo com essa informação.</p>
          ) : (
            <ol className="results__list">
              {result.results.map((s) => (
                <li key={`${s.rank}-${s.document_id}`}><SourceSlip source={s} query={result.query} onError={setError} /></li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

function snippets(lang: Lang, origin: string, base: KnowledgeBase, bot: Bot | null): { title: string; lead: string; code: string }[] {
  const k = "nxk_SUA_CHAVE";
  const b = base.id;
  const ask = bot
    ? { path: "/api/ask", body: `{"question": "Qual o horário de atendimento?", "bot_id": "${bot.id}"}`, py: `{"question": "Qual o horário de atendimento?", "bot_id": "${bot.id}"}` }
    : { path: "/api/search", body: `{"query": "horário de atendimento", "base_id": "${b}"}`, py: `{"query": "horário de atendimento", "base_id": "${b}"}` };
  if (lang === "curl") {
    return [
      { title: "Enviar arquivo", lead: "Qualquer formato aceito, um ou vários campos files.", code: `curl -X POST ${origin}/api/bases/${b}/documents \\\n  -H "X-API-Key: ${k}" \\\n  -F "files=@tabela-de-precos.pdf"` },
      { title: "Adicionar texto", lead: "Informação digitada, que entra na base na hora.", code: `curl -X POST ${origin}/api/bases/${b}/texts \\\n  -H "X-API-Key: ${k}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"title": "Horário", "content": "Atendemos de segunda a sexta, das 8h às 18h."}'` },
      { title: bot ? `Perguntar a ${bot.name}` : "Buscar nesta base", lead: bot ? "Resposta com fontes, usando só esta base." : "Trechos mais relevantes, sem gerar resposta.", code: `curl -X POST ${origin}${ask.path} \\\n  -H "X-API-Key: ${k}" \\\n  -H "Content-Type: application/json" \\\n  -d '${ask.body}'` },
      { title: "Remover item", lead: "Use o id devolvido no envio ou em GET /api/bases/{id}/documents.", code: `curl -X DELETE ${origin}/api/documents/ID_DO_ITEM \\\n  -H "X-API-Key: ${k}"` },
    ];
  }
  if (lang === "python") {
    return [
      { title: "Enviar arquivo", lead: "Qualquer formato aceito, um ou vários campos files.", code: `import requests\n\nwith open("tabela-de-precos.pdf", "rb") as arquivo:\n    r = requests.post(\n        "${origin}/api/bases/${b}/documents",\n        headers={"X-API-Key": "${k}"},\n        files=[("files", arquivo)],\n    )\nprint(r.json())` },
      { title: "Adicionar texto", lead: "Informação digitada, que entra na base na hora.", code: `import requests\n\nr = requests.post(\n    "${origin}/api/bases/${b}/texts",\n    headers={"X-API-Key": "${k}"},\n    json={"title": "Horário", "content": "Atendemos de segunda a sexta, das 8h às 18h."},\n)\nprint(r.json()["id"])` },
      { title: bot ? `Perguntar a ${bot.name}` : "Buscar nesta base", lead: bot ? "Resposta com fontes, usando só esta base." : "Trechos mais relevantes, sem gerar resposta.", code: `import requests\n\nr = requests.post(\n    "${origin}${ask.path}",\n    headers={"X-API-Key": "${k}"},\n    json=${ask.py},\n    timeout=120,\n).json()\nprint(r)` },
      { title: "Remover item", lead: "Use o id devolvido no envio ou em GET /api/bases/{id}/documents.", code: `import requests\n\nrequests.delete("${origin}/api/documents/ID_DO_ITEM", headers={"X-API-Key": "${k}"})` },
    ];
  }
  return [
    { title: "Enviar arquivo", lead: "Qualquer formato aceito, um ou vários campos files.", code: `const form = new FormData();\nform.append("files", arquivo);\n\nconst r = await fetch("${origin}/api/bases/${b}/documents", {\n  method: "POST",\n  headers: { "X-API-Key": "${k}" },\n  body: form,\n}).then((x) => x.json());` },
    { title: "Adicionar texto", lead: "Informação digitada, que entra na base na hora.", code: `await fetch("${origin}/api/bases/${b}/texts", {\n  method: "POST",\n  headers: { "X-API-Key": "${k}", "Content-Type": "application/json" },\n  body: JSON.stringify({ title: "Horário", content: "Atendemos de segunda a sexta, das 8h às 18h." }),\n});` },
    { title: bot ? `Perguntar a ${bot.name}` : "Buscar nesta base", lead: bot ? "Resposta com fontes, usando só esta base." : "Trechos mais relevantes, sem gerar resposta.", code: `const r = await fetch("${origin}${ask.path}", {\n  method: "POST",\n  headers: { "X-API-Key": "${k}", "Content-Type": "application/json" },\n  body: JSON.stringify(${ask.body}),\n}).then((x) => x.json());` },
    { title: "Remover item", lead: "Use o id devolvido no envio ou em GET /api/bases/{id}/documents.", code: `await fetch("${origin}/api/documents/ID_DO_ITEM", {\n  method: "DELETE",\n  headers: { "X-API-Key": "${k}" },\n});` },
  ];
}

function IntegrateTab({ base, bots }: { base: KnowledgeBase; bots: Bot[] }) {
  const [lang, setLang] = useState<Lang>("curl");
  const [step, setStep] = useState(0);
  const users = bots.filter((b) => b.base_id === base.id);
  const list = snippets(lang, window.location.origin, base, users[0] ?? null);
  const current = list[Math.min(step, list.length - 1)];

  return (
    <div className="kb-tab">
      <div className="kb-integrate">
        <div className="kb-id">
          <span>ID da base</span>
          <code>{base.id}</code>
          <CopyButton text={base.id} />
        </div>
        <p className="panel__lead">
          Envie a chave no cabeçalho <code>X-API-Key</code>. <Link to="/integracoes">Crie uma chave em Integrações</Link> e troque
          <code>nxk_SUA_CHAVE</code> nos exemplos.
        </p>
      </div>
      <div className="kb-recipes" role="tablist" aria-label="O que integrar">
        {list.map((s, i) => (
          <button key={s.title} role="tab" aria-selected={step === i} className={`kb-recipe${step === i ? " is-on" : ""}`} onClick={() => setStep(i)}>
            <span className="kb-recipe__n">{i + 1}</span>
            <strong>{s.title}</strong>
            <small>{s.lead}</small>
          </button>
        ))}
      </div>
      <div className="codebox">
        <div className="codebox__bar">
          <div className="segmented" role="tablist" aria-label="Linguagem">
            {(["curl", "python", "javascript"] as Lang[]).map((l) => (
              <button key={l} role="tab" aria-selected={lang === l} onClick={() => setLang(l)}>
                {l === "curl" ? "curl" : l === "python" ? "Python" : "JavaScript"}
              </button>
            ))}
          </div>
          <CopyButton text={current.code} />
        </div>
        <pre><code>{current.code}</code></pre>
      </div>
      <div className="kb-bots">
        <h3>Agentes que usam esta base</h3>
        {users.length === 0 ? (
          <p className="panel__lead">Nenhum agente ainda. <Link to="/agentes">Crie um agente</Link> e escolha esta base para ele responder com o que está aqui.</p>
        ) : (
          <ul>
            {users.map((b) => (
              <li key={b.id}>
                <span className="kb-dot" style={{ background: b.color }} aria-hidden="true" />
                <span className="kb-bots__name">{b.name}<small><code>{b.id}</code></small></span>
                <Link className="ghost-button small" to={`/chats?agente=${b.id}`}><Icon name="chats" size={15} />Conversar</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function BasesPage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [bases, setBases] = useState<KnowledgeBase[] | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const tab = (TABS.find((t) => t.id === params.get("aba"))?.id ?? "arquivos") as Tab;

  const loadBases = useCallback(() => api.bases().then(setBases).catch((e: ApiError) => toast(e.message, "error")), [toast]);
  useEffect(() => { void loadBases(); api.bots().then(setBots).catch(() => undefined); }, [loadBases]);

  const base = useMemo(() => {
    if (!bases) return null;
    return bases.find((b) => b.id === id) ?? bases.find((b) => b.is_default) ?? bases[0] ?? null;
  }, [bases, id]);

  const loadDocs = useCallback(() => {
    if (!base) return;
    api.baseDocuments(base.id).then(setDocs).catch(() => undefined);
    void loadBases();
  }, [base?.id, loadBases]);

  useEffect(() => {
    setDocs([]);
    setEditing(false);
    setConfirmDelete(false);
    setNotice(null);
    if (base) api.baseDocuments(base.id).then(setDocs).catch(() => undefined);
  }, [base?.id]);

  const working = docs.some((d) => d.status === "PENDING" || d.status === "PROCESSING");
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(loadDocs, 2000);
    return () => window.clearInterval(timer);
  }, [working, loadDocs]);

  function setTab(next: Tab) {
    setParams(next === "arquivos" ? {} : { aba: next }, { replace: true });
  }

  function onNotice(kind: "ok" | "error", text: string) {
    setNotice({ kind, text });
  }

  async function removeBase() {
    if (!base) return;
    try {
      await api.deleteBase(base.id);
      toast(`Base ${base.name} excluída.`);
      setConfirmDelete(false);
      await loadBases();
      navigate("/bases");
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  const lock = base?.is_default ? "A base padrão recebe os envios sem base escolhida e não pode ser excluída."
    : base && base.bots > 0 ? `${plural(base.bots, "agente usa", "agentes usam")} esta base. Troque a base deles antes de excluir.` : "";
  const ready = docs.filter((d) => d.status === "READY");
  const pages = ready.reduce((s, d) => s + d.pages, 0);
  const chunks = ready.reduce((s, d) => s + d.chunks, 0);

  return (
    <div className="page page--wide">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Agentes</span>
          <h1>Bases de conhecimento</h1>
          <p className="page__lead">Cada agente responde só com a base dele. Coloque e tire arquivos e textos quando quiser: o agente passa a usar na hora.</p>
        </div>
      </header>

      <div className="kb">
        <aside className="kb-list" aria-label="Bases">
          <div className="kb-list__head">
            <h2>Bases</h2>
            <button className="primary-button small" onClick={() => setCreating(true)}><Icon name="plus" size={16} />Nova</button>
          </div>
          {creating && (
            <BaseForm onCancel={() => setCreating(false)} onDone={(b) => {
              setCreating(false);
              toast(`Base ${b.name} criada. Agora adicione arquivos ou textos.`);
              void loadBases();
              navigate(`/bases/${b.id}`);
            }} />
          )}
          {bases === null ? <p className="kb-hint">Carregando…</p> : (
            <ul>
              {bases.map((b) => (
                <li key={b.id}>
                  <Link to={`/bases/${b.id}${tab === "arquivos" ? "" : `?aba=${tab}`}`} className={`kb-link${base?.id === b.id ? " is-on" : ""}`}>
                    <span className="kb-dot" style={{ background: b.color }} aria-hidden="true" />
                    <span className="kb-link__text">
                      <strong>{b.name}{b.is_default && <small className="kb-tag">padrão</small>}</strong>
                      <small>{plural(b.documents, "item", "itens")} · {b.bots ? plural(b.bots, "agente", "agentes") : "sem agente"}</small>
                    </span>
                    {b.processing > 0 && <span className="kb-busy" title="Indexando" aria-label="Indexando" />}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {base && (
          <section className="kb-main" aria-label={base.name}>
            {editing ? (
              <div className="kb-head kb-head--edit">
                <BaseForm initial={base} onCancel={() => setEditing(false)} onDone={() => { setEditing(false); toast("Base atualizada."); void loadBases(); }} />
              </div>
            ) : (
              <div className="kb-head">
                <span className="kb-dot kb-dot--big" style={{ background: base.color }} aria-hidden="true" />
                <div className="kb-head__titles">
                  <h2 className="fina">{base.name}</h2>
                  <p>{base.description || "Sem descrição."}</p>
                </div>
                <div className="kb-head__tools">
                  {base.can_edit && (
                    <button className="icon-button" title="Editar nome, descrição e cor" aria-label="Editar base" onClick={() => setEditing(true)}>
                      <Icon name="edit" />
                    </button>
                  )}
                  {base.can_edit && (
                    <button className="icon-button" title={lock || "Excluir base"} aria-label="Excluir base" disabled={!!lock}
                      onClick={() => setConfirmDelete(true)}>
                      <Icon name="trash" />
                    </button>
                  )}
                </div>
              </div>
            )}
            {lock && base.can_edit && !editing && <p className="kb-lock">{lock}</p>}
            {confirmDelete && (
              <div className="kb-confirm" role="alertdialog">
                <span>Excluir <b>{base.name}</b> com {plural(base.documents, "item", "itens")} e todos os trechos?</span>
                <button className="danger-button small" onClick={removeBase}>Excluir base</button>
                <button className="ghost-button small" onClick={() => setConfirmDelete(false)}>Manter</button>
              </div>
            )}

            <div className="box kb-summary">
              <section className="lid kb-lid" aria-label="Resumo da base">
                <span className="lid__label">Trechos indexados</span>
                <strong className="lid__number">{chunks.toLocaleString("pt-BR")}</strong>
                <dl className="lid__stats">
                  <div><dt>Itens</dt><dd>{docs.length}</dd></div>
                  <div><dt>Prontos</dt><dd>{ready.length}</dd></div>
                  <div><dt>Páginas e partes</dt><dd>{pages.toLocaleString("pt-BR")}</dd></div>
                  <div><dt>Agentes</dt><dd>{base.bots}</dd></div>
                </dl>
              </section>
              <section className="kb-tabs">
                <div className="segmented kb-segmented" role="tablist" aria-label="Seções da base">
                  {TABS.map((t) => (
                    <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                      {t.label}
                      {t.id === "arquivos" && <small>{docs.filter((d) => d.kind !== "note").length}</small>}
                      {t.id === "textos" && <small>{docs.filter((d) => d.kind === "note").length}</small>}
                    </button>
                  ))}
                </div>
                {notice && <p className={notice.kind === "ok" ? "alert alert--ok" : "alert"} role="status">{notice.text}</p>}
                {docs.length === 0 && (tab === "arquivos" || tab === "textos") && (
                  <div className="kb-empty">
                    <strong>Esta base está vazia</strong>
                    <p>Escolha um jeito de colocar conhecimento nela:</p>
                    <ol>
                      <li><Icon name="upload" size={16} /><span><b>Arraste arquivos</b> PDF, Word, planilhas CSV, textos e páginas HTML.</span></li>
                      <li><Icon name="text" size={16} /><span><b>Escreva um texto</b> com preços, horários e regras, na aba <button className="link-button" onClick={() => setTab("textos")}>Textos</button>.</span></li>
                      <li><Icon name="link" size={16} /><span><b>Integre por API</b> para outro sistema alimentar a base, na aba <button className="link-button" onClick={() => setTab("integrar")}>Integrar</button>.</span></li>
                    </ol>
                  </div>
                )}
                {tab === "arquivos" && <FilesTab base={base} bases={bases ?? []} docs={docs} reload={loadDocs} onNotice={onNotice} />}
                {tab === "textos" && <TextsTab base={base} docs={docs} reload={loadDocs} onNotice={onNotice} />}
                {tab === "testar" && <TestTab base={base} />}
                {tab === "integrar" && <IntegrateTab base={base} bots={bots} />}
              </section>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
