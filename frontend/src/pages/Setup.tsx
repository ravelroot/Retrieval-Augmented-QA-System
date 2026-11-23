import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api, type ProbeResult, type SettingItem, type SetupState } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { Icon } from "../components/Icon";
import { Brand } from "../components/Logo";
import { useToast } from "../components/Toast";
import { PRESETS, presetFor, type Preset } from "../providers";

const DEFAULT_PASSWORD = "Nexo@2026";

type StepId = "senha" | "ia" | "acesso" | "pronto";

const LABELS: Record<StepId, { title: string; lead: string }> = {
  senha: { title: "Nova senha", lead: "A conta admin ainda usa a senha que vem com o Nexo. Escolha uma só sua antes de continuar." },
  ia: { title: "Inteligência", lead: "Escolha quem escreve as respostas. Os documentos continuam no seu computador; só os trechos relevantes vão para o modelo." },
  acesso: { title: "Acesso e proteção", lead: "Como as pessoas chegam ao Nexo e como os dados ficam protegidos." },
  pronto: { title: "Tudo pronto", lead: "Siga os próximos passos quando quiser. Esta lista fica em Sistema e conta." },
};

export function rememberSetup(): void {
  try {
    sessionStorage.setItem("nexo.assistente", "visto");
  } catch {
    return;
  }
}

function valueOf(items: SettingItem[], name: string): string | number | boolean | undefined {
  return items.find((i) => i.name === name)?.value;
}

function PasswordStep({ onDone }: { onDone: () => void }) {
  const { signIn } = useAuth();
  const [form, setForm] = useState({ next: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    if (form.next !== form.confirm) {
      setErrors({ confirm: "As senhas não conferem." });
      return;
    }
    setBusy(true);
    try {
      signIn(await api.changePassword(DEFAULT_PASSWORD, form.next));
      onDone();
    } catch (err) {
      const apiError = err as ApiError;
      const fields = apiError.fields ?? {};
      setErrors({ next: fields.password ?? fields.new_password ?? "", ...(Object.keys(fields).length ? {} : { form: apiError.message }) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="setup__form" onSubmit={submit} noValidate>
      <Field label="Nova senha" name="setup-password" type="password" autoComplete="new-password" value={form.next} autoFocus
        onChange={(e) => setForm({ ...form, next: e.target.value })} error={errors.next}
        hint="De 8 a 72 caracteres, com letras e números, sem conter o nome de usuário." />
      <Field label="Repita a nova senha" name="setup-confirm" type="password" autoComplete="new-password" value={form.confirm}
        onChange={(e) => setForm({ ...form, confirm: e.target.value })} error={errors.confirm} />
      {errors.form && <p className="alert" role="alert">{errors.form}</p>}
      <div className="setup__actions">
        <button className="primary-button" type="submit" disabled={busy || !form.next || !form.confirm}>
          {busy ? "Salvando…" : "Salvar senha e continuar"}
        </button>
      </div>
    </form>
  );
}

function IntelligenceStep({ items, onSaved }: { items: SettingItem[]; onSaved: () => void }) {
  const toast = useToast();
  const initial = presetFor(String(valueOf(items, "llm_provider") ?? "ollama"), String(valueOf(items, "openai_base_url") ?? ""));
  const keyConfigured = !!items.find((i) => i.name === "openai_api_key")?.configured;
  const [preset, setPreset] = useState<Preset>(initial);
  const [ollamaUrl, setOllamaUrl] = useState(String(valueOf(items, "ollama_url") ?? "http://localhost:11434"));
  const [baseUrl, setBaseUrl] = useState(String(valueOf(items, "openai_base_url") ?? ""));
  const [model, setModel] = useState(String(valueOf(items, "llm_model") ?? ""));
  const [key, setKey] = useState("");
  const [installed, setInstalled] = useState<string[] | null>(null);
  const [ollamaError, setOllamaError] = useState("");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"test" | "save" | "list" | null>(null);

  const initialModel = String(valueOf(items, "llm_model") ?? "");
  const initialUrl = String(valueOf(items, "openai_base_url") ?? "");

  function choose(next: Preset) {
    const same = next.id === initial.id;
    setPreset(next);
    setProbe(null);
    setFields({});
    setBaseUrl(next.baseUrl ?? (same ? initialUrl : ""));
    setModel(same ? initialModel : next.model ?? "");
  }

  async function listModels() {
    setBusy("list");
    try {
      const out = await api.ollamaModels(ollamaUrl);
      setInstalled(out.models);
      setOllamaError(out.error ?? (out.models.length ? "" : "O Ollama respondeu, mas não tem modelos. Rode ollama pull llama3.1."));
      if (out.models.length && !out.models.some((m) => m === model || m.split(":")[0] === model)) setModel(out.models[0].split(":")[0]);
    } catch (e) {
      setOllamaError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => { if (preset.provider === "ollama") void listModels(); }, [preset.provider]);

  const values = useMemo(() => {
    const out: Record<string, string> = { llm_provider: preset.provider };
    if (preset.provider === "extrativo") return out;
    out.llm_model = model.trim();
    if (preset.provider === "ollama") out.ollama_url = ollamaUrl.trim();
    if (preset.provider === "compativel") out.openai_base_url = baseUrl.trim();
    if (preset.provider === "openai") out.openai_base_url = "";
    if (key.trim()) out.openai_api_key = key.trim();
    return out;
  }, [preset, model, ollamaUrl, baseUrl, key]);

  const missing = preset.provider !== "extrativo" && (!model.trim() || (preset.provider === "compativel" && !baseUrl.trim())
    || (preset.needsKey && !key.trim() && !keyConfigured));

  async function test() {
    setBusy("test");
    setFields({});
    try {
      setProbe(await api.testProvider("llm", values));
    } catch (e) {
      const apiError = e as ApiError;
      setFields(apiError.fields ?? {});
      setProbe({ target: "llm", ok: false, detail: apiError.message, latency_ms: 0 });
    } finally {
      setBusy(null);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy("save");
    setFields({});
    try {
      await api.saveSettings(values);
      toast(preset.provider === "extrativo" ? "Modo sem modelo salvo." : `${preset.label} configurado.`);
      onSaved();
    } catch (err) {
      const apiError = err as ApiError;
      setFields(apiError.fields ?? {});
      toast(apiError.message, "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <form className="setup__form setup__form--wide" onSubmit={save} noValidate>
      <div className="setup-presets" role="radiogroup" aria-label="Provedor do modelo">
        {PRESETS.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={preset.id === p.id}
            className={`setup-preset${preset.id === p.id ? " is-on" : ""}`} onClick={() => choose(p)}>
            <strong>{p.label}</strong>
            <span>{p.hint}</span>
          </button>
        ))}
      </div>

      {preset.provider === "ollama" && (
        <div className="setup-grid">
          <Field label="Endereço do Ollama" name="ollama-url" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)}
            error={fields.ollama_url} hint="No mesmo computador: http://localhost:11434." />
          <div className="field">
            <label htmlFor="ollama-model">Modelo</label>
            {installed && installed.length > 0 ? (
              <select id="ollama-model" className="setup-select" value={model} onChange={(e) => setModel(e.target.value)}>
                {!installed.some((m) => m === model || m.split(":")[0] === model) && model && <option value={model}>{model}</option>}
                {installed.map((m) => <option key={m} value={m.endsWith(":latest") ? m.slice(0, -7) : m}>{m}</option>)}
              </select>
            ) : (
              <input id="ollama-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="llama3.1" />
            )}
            <p className={ollamaError ? "field__message" : "field__hint"}>
              {ollamaError || (installed ? `${installed.length} modelo(s) instalado(s).` : "Procurando os modelos instalados…")}
              {" "}<button type="button" className="link-button" onClick={listModels} disabled={busy === "list"}>Atualizar lista</button>
            </p>
          </div>
          <div className="setup-tip">
            <b>Ainda não tem o Ollama?</b>
            <span>Instale em <a href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com</a> e rode <code>ollama pull llama3.1</code> no terminal.</span>
          </div>
        </div>
      )}

      {(preset.provider === "openai" || preset.provider === "compativel") && (
        <div className="setup-grid">
          {preset.provider === "compativel" && (
            <Field label="Endereço do serviço" name="base-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              readOnly={!preset.editableUrl && !!preset.baseUrl} error={fields.openai_base_url}
              hint={preset.editableUrl ? "O endereço que termina em /v1." : "Preenchido para você."} placeholder="https://servidor/v1" />
          )}
          <Field label={preset.needsKey ? "Chave da API" : "Chave da API (se o serviço pedir)"} name="api-key" type="password"
            autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} error={fields.openai_api_key}
            placeholder={keyConfigured ? "•••••••• já configurada" : "Cole a chave aqui"}
            hint={keyConfigured ? "Deixe em branco para manter a chave atual." : "Fica só neste computador, em segredos.json."} />
          <Field label="Modelo" name="model" value={model} onChange={(e) => setModel(e.target.value)} error={fields.llm_model}
            placeholder={preset.modelExample ? `ex.: ${preset.modelExample}` : ""}
            hint="Use o nome exato do modelo, como aparece na lista do serviço." />
          {preset.keyUrl && (
            <div className="setup-tip">
              <b>Onde pegar a chave</b>
              <span><a href={preset.keyUrl} target="_blank" rel="noreferrer">{preset.keyUrl.replace("https://", "")}</a></span>
            </div>
          )}
        </div>
      )}

      {preset.provider === "extrativo" && (
        <p className="setup-tip"><b>Bom para conferir a instalação.</b><span>As respostas mostram as frases mais relevantes dos trechos, com a fonte, sem um modelo redigindo. Troque depois em Sistema e conta → Ajustes.</span></p>
      )}

      {probe && (
        <p className={`setup-probe ${probe.ok ? "is-ok" : "is-bad"}`} role="status">
          <Icon name={probe.ok ? "check" : "close"} size={16} />
          <span>{probe.detail}{probe.ok && probe.latency_ms ? ` (${(probe.latency_ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s)` : ""}</span>
        </p>
      )}

      <div className="setup__actions">
        <button className="ghost-button" type="button" onClick={test} disabled={!!busy || missing}>
          <Icon name="bolt" size={16} />{busy === "test" ? "Testando…" : "Testar conexão"}
        </button>
        <button className="primary-button" type="submit" disabled={!!busy || missing}>
          {busy === "save" ? "Salvando…" : "Salvar e continuar"}
        </button>
      </div>
    </form>
  );
}

function AccessStep({ items, onSaved }: { items: SettingItem[]; onSaved: () => void }) {
  const toast = useToast();
  const [publicUrl, setPublicUrl] = useState(String(valueOf(items, "public_url") ?? ""));
  const [registration, setRegistration] = useState(!!valueOf(items, "allow_registration"));
  const [backup, setBackup] = useState(true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const suggestion = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "" : window.location.origin;

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFields({});
    try {
      const hours = Number(valueOf(items, "backup_hours") ?? 0);
      await api.saveSettings({ public_url: publicUrl.trim(), allow_registration: registration, backup_hours: backup ? (hours || 24) : 0 });
      toast("Acesso e proteção salvos.");
      onSaved();
    } catch (err) {
      const apiError = err as ApiError;
      setFields(apiError.fields ?? {});
      toast(apiError.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="setup__form" onSubmit={save} noValidate>
      <Field label="Endereço público do Nexo (opcional)" name="public-url" value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)}
        error={fields.public_url} placeholder={suggestion || "https://nexo.suaempresa.com.br"}
        hint="Preencha quando o Nexo estiver na internet: o WhatsApp e o widget para sites usam este endereço." />
      {suggestion && !publicUrl && (
        <button type="button" className="link-button setup-suggest" onClick={() => setPublicUrl(suggestion)}>Usar {suggestion}</button>
      )}
      <label className="check setup-check">
        <input type="checkbox" checked={backup} onChange={(e) => setBackup(e.target.checked)} />
        <span><b>Backup automático todo dia</b><small>Guarda os 7 mais recentes na pasta backups. Dá para baixar em Sistema e conta → Manutenção.</small></span>
      </label>
      <label className="check setup-check">
        <input type="checkbox" checked={registration} onChange={(e) => setRegistration(e.target.checked)} />
        <span><b>Qualquer pessoa pode criar a própria conta</b><small>Desligue para que só administradores criem contas.</small></span>
      </label>
      <div className="setup__actions">
        <button className="primary-button" type="submit" disabled={busy}>{busy ? "Salvando…" : "Salvar e continuar"}</button>
      </div>
    </form>
  );
}

export function Checklist({ state, compact = false }: { state: SetupState; compact?: boolean }) {
  return (
    <ol className={`checklist${compact ? " checklist--compact" : ""}`}>
      {state.steps.map((s) => (
        <li key={s.id} className={s.done ? "is-done" : ""}>
          <span className="checklist__mark" aria-hidden="true">{s.done ? <Icon name="check" size={14} /> : null}</span>
          <div>
            <strong>{s.label}</strong>
            <p>{s.detail}</p>
          </div>
          {!s.done && s.to && <Link className="ghost-button small" to={s.to}>Abrir</Link>}
          <span className="sr-only">{s.done ? "Concluído" : "Pendente"}</span>
        </li>
      ))}
    </ol>
  );
}

function ReadyStep({ state, onFinish, onReload }: { state: SetupState; onFinish: (to: string) => void; onReload: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const content = state.steps.find((s) => s.id === "content");

  async function sample() {
    setBusy(true);
    try {
      const out = await api.createSample();
      toast(out.existed && !out.added ? "A base de teste já existia." : `Base de teste criada com o ${out.bot.name}. A indexação segue em segundo plano.`);
      onReload();
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="setup__form setup__form--wide">
      <Checklist state={state} />
      <div className="setup__actions">
        {content && !content.done && (
          <button className="ghost-button" type="button" onClick={sample} disabled={busy}>
            <Icon name="sparkle" size={16} />{busy ? "Criando…" : "Criar base de teste"}
          </button>
        )}
        <button className="primary-button" type="button" onClick={() => onFinish(content?.done ? "/chats" : "/bases")}>
          {content?.done ? "Concluir e conversar com os agentes" : "Concluir e montar a primeira base"}
        </button>
      </div>
    </div>
  );
}

export function SetupPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [state, setState] = useState<SetupState | null>(null);
  const [items, setItems] = useState<SettingItem[] | null>(null);
  const [step, setStep] = useState<StepId | null>(null);
  const [withPassword, setWithPassword] = useState(false);
  const [error, setError] = useState("");

  const load = async (first = false) => {
    try {
      const next = await api.setup();
      setState(next);
      if (!next.must_change_password) setItems((await api.settings()).items);
      if (first) {
        setWithPassword(next.must_change_password);
        setStep(next.must_change_password ? "senha" : "ia");
      }
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => { void load(true); }, []);

  const order: StepId[] = withPassword ? ["senha", "ia", "acesso", "pronto"] : ["ia", "acesso", "pronto"];
  const index = step ? order.indexOf(step) : 0;

  async function advance() {
    await load();
    setStep(order[Math.min(index + 1, order.length - 1)]);
  }

  async function finish(to: string) {
    try {
      await api.finishSetup(true);
      rememberSetup();
      toast("Configuração concluída. A lista de próximos passos fica em Sistema e conta.");
      navigate(to, { replace: true });
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  if (user?.role !== "admin") {
    return (
      <div className="setup setup--plain">
        <p className="alert">Só administradores configuram o Nexo. <Link to="/conversas">Voltar</Link></p>
      </div>
    );
  }

  const label = step ? LABELS[step] : null;
  return (
    <div className="setup">
      <aside className="setup__side">
        <Brand subtitle="Configuração" inverted />
        <ol className="setup__steps">
          {order.map((id, i) => (
            <li key={id} className={i < index ? "is-done" : i === index ? "is-on" : ""}>
              <span>{i < index ? <Icon name="check" size={13} /> : i + 1}</span>{LABELS[id].title}
            </li>
          ))}
        </ol>
        <p className="setup__note">Tudo aqui muda depois em Sistema e conta → Ajustes, sem editar arquivos nem reiniciar.</p>
      </aside>
      <main className="setup__main">
        <div className="setup__top">
          <span className="page__over">Passo {index + 1} de {order.length}</span>
          {step !== "senha" && !state?.must_change_password && (
            <button className="link-button" type="button" onClick={() => finish("/conversas")}>Pular por agora</button>
          )}
        </div>
        {error && <p className="alert" role="alert">{error}</p>}
        {label && (
          <header className="setup__head">
            <h1>{label.title}</h1>
            <p>{label.lead}</p>
          </header>
        )}
        {step === "senha" && <PasswordStep onDone={advance} />}
        {step === "ia" && items && <IntelligenceStep items={items} onSaved={advance} />}
        {step === "acesso" && items && <AccessStep items={items} onSaved={advance} />}
        {step === "pronto" && state && <ReadyStep state={state} onFinish={finish} onReload={() => void load()} />}
        {index > 0 && step !== "pronto" && order[index - 1] !== "senha" && (
          <button className="link-button setup__back" type="button" onClick={() => setStep(order[index - 1])}>
            <Icon name="arrowLeft" size={14} />Voltar
          </button>
        )}
      </main>
    </div>
  );
}
