import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, api, downloadAudit, downloadBackup, type AuditPage, type Check, type Diagnostics, type MaintenanceAction,
  type SettingItem, type SettingsData, type SystemStatus, type User } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { Icon } from "../components/Icon";
import { openTutorial } from "../components/Shell";
import { useToast } from "../components/Toast";
import { formatDateTime, plural } from "../format";

type Tab = "geral" | "ajustes" | "diagnostico" | "manutencao" | "atividades" | "contas";

const TABS: { id: Tab; label: string }[] = [
  { id: "geral", label: "Visão geral" },
  { id: "ajustes", label: "Ajustes" },
  { id: "diagnostico", label: "Diagnóstico" },
  { id: "manutencao", label: "Manutenção" },
  { id: "atividades", label: "Atividades" },
  { id: "contas", label: "Contas" },
];

const EMPTY_ACCOUNT = { name: "", username: "", password: "", role: "user" as User["role"] };

function show(value: SettingItem["value"]): string {
  if (typeof value === "boolean") return value ? "Ligado" : "Desligado";
  if (typeof value === "number") return value.toLocaleString("pt-BR");
  return value;
}

function Users({ me }: { me: string }) {
  const toast = useToast();
  const [users, setUsers] = useState<User[] | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [account, setAccount] = useState(EMPTY_ACCOUNT);
  const [accountErrors, setAccountErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const load = () => api.users().then(setUsers).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => { void load(); }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setAccountErrors({});
    setBusy(true);
    try {
      const created = await api.createUser(account);
      toast(`Conta de ${created.name} criada. Passe a senha inicial para a pessoa por um canal seguro.`);
      setAccount(EMPTY_ACCOUNT);
      setCreating(false);
      void load();
    } catch (err) {
      const apiError = err as ApiError;
      const fields = apiError.fields ?? {};
      setAccountErrors(Object.keys(fields).length ? fields : { form: apiError.message });
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent, username: string) {
    e.preventDefault();
    try {
      await api.resetPassword(username, newPassword);
      toast("Senha redefinida. As sessões abertas dessa conta foram encerradas.");
      setResetting(null);
      setNewPassword("");
      void load();
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  async function run(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      toast(done);
      setConfirm(null);
      void load();
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  if (!users) return null;
  const q = filter.trim().toLowerCase();
  const visible = users.filter((u) => !q || u.name.toLowerCase().includes(q) || u.username.includes(q));
  return (
    <div className="box">
      <section className="panel">
        <h2>Contas</h2>
        <p className="panel__lead">Crie contas, promova quem administra o acervo, redefina senhas esquecidas e exclua contas que não usam mais o Nexo. Excluir uma conta apaga também as conversas e as chaves de API dela. Redefinir a senha encerra as sessões abertas da pessoa.</p>
        {creating ? (
          <form className="password-form" onSubmit={create} noValidate>
            <h3>Nova conta</h3>
            <Field label="Nome" name="new-name" value={account.name} autoComplete="off"
              onChange={(e) => setAccount({ ...account, name: e.target.value })} error={accountErrors.name} />
            <Field label="Usuário" name="new-username" value={account.username} autoComplete="off"
              onChange={(e) => setAccount({ ...account, username: e.target.value })} error={accountErrors.username}
              hint="De 3 a 32 letras minúsculas, números, ponto, hífen ou sublinhado." />
            <Field label="Senha inicial" name="new-password" type="password" value={account.password} autoComplete="new-password"
              onChange={(e) => setAccount({ ...account, password: e.target.value })} error={accountErrors.password}
              hint="De 8 a 72 caracteres, com letras e números." />
            <label className="check">
              <input type="checkbox" checked={account.role === "admin"}
                onChange={(e) => setAccount({ ...account, role: e.target.checked ? "admin" : "user" })} />
              Administrador
            </label>
            {accountErrors.form && <p className="alert" role="alert">{accountErrors.form}</p>}
            <span className="panel__actions">
              <button className="primary-button" type="submit" disabled={busy || !account.name || !account.username || !account.password}>
                {busy ? "Criando…" : "Criar conta"}
              </button>
              <button className="ghost-button" type="button" onClick={() => { setCreating(false); setAccountErrors({}); }}>Cancelar</button>
            </span>
          </form>
        ) : (
          <div className="panel__actions">
            <button className="ghost-button" type="button" onClick={() => setCreating(true)}>
              <Icon name="plus" size={16} />Nova conta
            </button>
            {users.length > 6 && (
              <input className="toolbar__search ops-filter" value={filter} onChange={(e) => setFilter(e.target.value)}
                placeholder="Filtrar por nome ou usuário" aria-label="Filtrar contas" />
            )}
          </div>
        )}
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Nome</th><th>Usuário</th><th>Perfil</th><th>Último acesso</th><th><span className="sr-only">Ações</span></th></tr></thead>
            <tbody>
              {visible.map((u) => (
                <tr key={u.username}>
                  <td>{u.name}{u.username === me && <span className="muted"> (você)</span>}</td>
                  <td><code>{u.username}</code></td>
                  <td>
                    <select aria-label={`Perfil de ${u.name}`} value={u.role} disabled={u.username === me}
                      onChange={(e) => run(() => api.setRole(u.username, e.target.value as User["role"]), "Perfil alterado.")}>
                      <option value="user">Usuário</option>
                      <option value="admin">Administrador</option>
                    </select>
                  </td>
                  <td>{u.last_login_at ? formatDateTime(u.last_login_at) : "Nunca entrou"}</td>
                  <td className="table__actions">
                    {u.username === me ? null : resetting === u.username ? (
                      <form className="inline-form" onSubmit={(e) => reset(e, u.username)}>
                        <input type="password" aria-label={`Nova senha de ${u.name}`} placeholder="Nova senha" autoFocus
                          autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                          onKeyDown={(e) => e.key === "Escape" && setResetting(null)} />
                        <button className="primary-button small" type="submit" disabled={newPassword.length < 8}>Salvar</button>
                        <button className="ghost-button small" type="button" onClick={() => setResetting(null)}>Cancelar</button>
                      </form>
                    ) : confirm === u.username ? (
                      <>
                        <button className="danger-button small" onClick={() => run(() => api.deleteUser(u.username), "Conta excluída.")}>Excluir</button>
                        <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                      </>
                    ) : (
                      <>
                        <button className="link-button" onClick={() => { setResetting(u.username); setNewPassword(""); }}>Redefinir senha</button>
                        <button className="link-button link-button--danger" onClick={() => setConfirm(u.username)}>Excluir</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function SettingsPanel({ onReindex }: { onReindex: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<SettingsData | null>(null);
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [reindex, setReindex] = useState(false);

  function fill(next: SettingsData) {
    setData(next);
    setDraft(Object.fromEntries(next.items.map((i) => [i.name, typeof i.value === "boolean" ? i.value : String(i.value)])));
  }

  useEffect(() => { api.settings().then(fill).catch((e: ApiError) => toast(e.message, "error")); }, []);

  const groups = useMemo(() => {
    const out: { name: string; items: SettingItem[] }[] = [];
    for (const item of data?.items ?? []) {
      const found = out.find((g) => g.name === item.group);
      if (found) found.items.push(item);
      else out.push({ name: item.group, items: [item] });
    }
    return out;
  }, [data]);

  function parsed(item: SettingItem): string | number | boolean {
    const raw = draft[item.name];
    if (item.kind === "bool") return !!raw;
    if (item.kind === "int") return Number.parseInt(String(raw), 10);
    if (item.kind === "float") return Number.parseFloat(String(raw).replace(",", "."));
    return String(raw ?? "");
  }

  const changes = useMemo(() => {
    const out: Record<string, string | number | boolean> = {};
    for (const item of data?.items ?? []) {
      const value = parsed(item);
      if (value !== item.value && !(typeof value === "number" && Number.isNaN(value) && item.value === "")) out[item.name] = value;
    }
    return out;
  }, [draft, data]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!Object.keys(changes).length) return;
    setBusy(true);
    setFields({});
    try {
      const next = await api.saveSettings(changes);
      fill(next);
      setReindex(!!next.reindex_needed);
      toast(next.changed?.length ? `${plural(next.changed.length, "ajuste salvo", "ajustes salvos")}. Já vale para as próximas perguntas.` : "Nada mudou.");
    } catch (err) {
      const apiError = err as ApiError;
      setFields(apiError.fields ?? {});
      toast(apiError.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function restore(names?: string[]) {
    try {
      const next = await api.resetSettings(names);
      fill(next);
      setFields({});
      setReindex(!!next.reindex_needed);
      toast(names ? "Valor padrão restaurado." : "Todos os ajustes voltaram ao padrão do .env.");
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  if (!data) return <div className="box"><section className="panel"><p className="panel__lead">Carregando os ajustes…</p></section></div>;
  const overridden = data.items.filter((i) => i.overridden).length;
  return (
    <>
      <div className="box">
        <form className="panel ops-settings" onSubmit={save} noValidate>
          <div className="ops-head">
            <div>
              <h2>Ajustes pela tela</h2>
              <p className="panel__lead">Valem na hora, sem reiniciar o servidor, e ficam guardados em <code>data/ajustes.json</code> por cima do <code>.env</code>. {overridden ? `${plural(overridden, "item diferente", "itens diferentes")} do padrão.` : "Tudo no padrão do .env."}</p>
            </div>
            <span className="panel__actions">
              {overridden > 0 && <button className="ghost-button small" type="button" onClick={() => restore()}>Restaurar padrões</button>}
              <button className="primary-button small" type="submit" disabled={busy || !Object.keys(changes).length}>
                <Icon name="check" size={15} />{busy ? "Salvando…" : Object.keys(changes).length ? `Salvar ${plural(Object.keys(changes).length, "ajuste", "ajustes")}` : "Salvar"}
              </button>
            </span>
          </div>
          {(reindex || data.outdated > 0) && (
            <div className="ops-callout" role="status">
              <span><b>{plural(data.outdated, "documento indexado", "documentos indexados")} com a configuração anterior.</b> Reindexe para os trechos seguirem o novo tamanho.</span>
              <button className="ghost-button small" type="button" onClick={onReindex}><Icon name="refresh" size={15} />Reindexar desatualizados</button>
            </div>
          )}
          {groups.map((group) => (
            <fieldset key={group.name} className="ops-group">
              <legend>{group.name}</legend>
              <div className="ops-fields">
                {group.items.map((item) => {
                  const id = `ajuste-${item.name}`;
                  const error = fields[item.name];
                  const dirty = item.name in changes;
                  return (
                    <div key={item.name} className={`ops-field${error ? " field--error" : ""}${dirty ? " is-dirty" : ""}`}>
                      {item.kind === "bool" ? (
                        <label className="check ops-check" htmlFor={id}>
                          <input id={id} type="checkbox" checked={!!draft[item.name]}
                            onChange={(e) => setDraft({ ...draft, [item.name]: e.target.checked })} />
                          <span><b>{item.label}</b><small>{item.hint}</small></span>
                        </label>
                      ) : (
                        <>
                          <label htmlFor={id}>{item.label}{item.reindex && <span className="ops-tag">reindexa</span>}</label>
                          <input id={id} type={item.kind === "text" ? "text" : "number"} value={String(draft[item.name] ?? "")}
                            step={item.kind === "float" ? "any" : 1} min={item.min ?? undefined} max={item.max ?? undefined}
                            aria-invalid={!!error} aria-describedby={`${id}-dica`}
                            onChange={(e) => setDraft({ ...draft, [item.name]: e.target.value })} />
                          <p className={error ? "field__message" : "field__hint"} id={`${id}-dica`}>{error ?? item.hint}</p>
                        </>
                      )}
                      {item.overridden && (
                        <p className="ops-default">Padrão do .env: {show(item.default)} <button type="button" className="link-button" onClick={() => restore([item.name])}>restaurar</button></p>
                      )}
                    </div>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </form>
      </div>
      <div className="box">
        <section className="panel">
          <h2>Definidos no .env</h2>
          <p className="panel__lead">Trocar estes itens exige editar o <code>.env</code> e reiniciar, porque mudam o modelo de embeddings, o banco ou a segurança. O passo a passo está no <code>Manual-Nexo.pdf</code>.</p>
          <dl className="config">
            {Object.entries(data.fixed).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
          </dl>
        </section>
      </div>
    </>
  );
}

function CheckRow({ check }: { check: Check }) {
  return (
    <li className={`ops-check-row ops-check-row--${check.status}`}>
      <span className="ops-dot" aria-hidden="true" />
      <div>
        <strong>{check.label}</strong>
        <p>{check.detail}</p>
        {check.hint && check.status !== "ok" && <p className="ops-hint">{check.hint}</p>}
      </div>
      <span className="ops-status">{{ ok: "Ok", warn: "Atenção", fail: "Falha", info: "Info" }[check.status]}</span>
    </li>
  );
}

function DiagnosticsPanel() {
  const toast = useToast();
  const [report, setReport] = useState<Diagnostics | null>(null);
  const [busy, setBusy] = useState<"rapido" | "completo" | null>(null);

  async function run(deep: boolean) {
    setBusy(deep ? "completo" : "rapido");
    try {
      setReport(await api.diagnostics(deep));
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => { void run(false); }, []);

  const groups = useMemo(() => {
    const out: { name: string; checks: Check[] }[] = [];
    for (const c of report?.checks ?? []) {
      const found = out.find((g) => g.name === c.group);
      if (found) found.checks.push(c);
      else out.push({ name: c.group, checks: [c] });
    }
    return out;
  }, [report]);

  return (
    <div className="box box--ops">
      <section className="lid" aria-label="Resumo do diagnóstico">
        <span className="lid__label">{report?.deep ? "Diagnóstico completo" : "Diagnóstico rápido"}</span>
        <strong className="lid__number">{report ? report.fail : "—"}</strong>
        <p className="lid__sub">{report ? (report.fail ? plural(report.fail, "falha precisa de atenção", "falhas precisam de atenção") : "Nenhuma falha encontrada.") : "Conferindo…"}</p>
        <dl className="lid__stats">
          <div><dt>Ok</dt><dd>{report?.ok ?? 0}</dd></div>
          <div><dt>Atenção</dt><dd>{report?.warn ?? 0}</dd></div>
          <div><dt>Falhas</dt><dd>{report?.fail ?? 0}</dd></div>
          <div><dt>Conferido</dt><dd>{report ? formatDateTime(report.checked_at).split(" ").pop() : "—"}</dd></div>
        </dl>
      </section>
      <section className="panel">
        <div className="ops-head">
          <div>
            <h2>O que foi conferido</h2>
            <p className="panel__lead">O rápido olha banco, disco, segurança, acervo e integrações. O completo também carrega os modelos e faz uma chamada de teste, por isso pode levar alguns segundos. Pela linha de comando: <code>python -m nexo diagnostico</code>.</p>
          </div>
          <span className="panel__actions">
            <button className="ghost-button small" onClick={() => run(false)} disabled={!!busy}><Icon name="refresh" size={15} />{busy === "rapido" ? "Conferindo…" : "Rodar de novo"}</button>
            <button className="primary-button small" onClick={() => run(true)} disabled={!!busy}><Icon name="bolt" size={15} />{busy === "completo" ? "Testando os modelos…" : "Diagnóstico completo"}</button>
          </span>
        </div>
        {busy && <div className="busline" aria-hidden="true"><span /></div>}
        {groups.map((g) => (
          <div key={g.name} className="ops-checks">
            <h3>{g.name}</h3>
            <ul>{g.checks.map((c) => <CheckRow key={c.id} check={c} />)}</ul>
          </div>
        ))}
      </section>
    </div>
  );
}

const MAINTENANCE: { action: MaintenanceAction; title: string; text: string; confirm?: string; icon: string }[] = [
  { action: "reindex_failed", title: "Reindexar falhas", text: "Tenta de novo os documentos que falharam na indexação.", icon: "refresh" },
  { action: "reindex_outdated", title: "Reindexar desatualizados", text: "Refaz os trechos dos documentos indexados com outra configuração de embeddings ou de tamanho do trecho.", icon: "refresh" },
  { action: "reindex_all", title: "Reindexar tudo", text: "Refaz os trechos do acervo inteiro. Use depois de trocar o modelo de embeddings no .env.", confirm: "O acervo inteiro volta para a fila. Continuar?", icon: "refresh" },
  { action: "clean_orphans", title: "Limpar órfãos", text: "Apaga arquivos de uploads e vetores que não pertencem a nenhum documento.", confirm: "Apagar arquivos e vetores sem documento?", icon: "trash" },
  { action: "vacuum", title: "Compactar o banco", text: "Recupera o espaço do SQLite depois de muitas exclusões.", icon: "base" },
];

function MaintenancePanel({ status, onDone }: { status: SystemStatus | null; onDone: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [days, setDays] = useState("90");
  const [result, setResult] = useState<string>("");

  async function run(action: MaintenanceAction, extra?: number) {
    setBusy(action);
    setConfirm(null);
    try {
      const out = await api.maintenance(action, extra);
      setResult(out.message);
      toast(out.message);
      onDone();
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(null);
    }
  }

  async function backup() {
    setBusy("backup");
    try {
      await downloadBackup();
      toast("Backup baixado. Guarde o arquivo em local seguro: ele tem as contas, os segredos e os documentos.");
      onDone();
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(null);
    }
  }

  const failed = status?.documents.by_status.FAILED ?? 0;
  const outdated = status?.documents.outdated ?? 0;
  return (
    <>
      {result && <p className="alert alert--ok" role="status">{result}</p>}
      <div className="box box--two">
        <section className="panel ops-backup">
          <h2>Backup</h2>
          <p className="panel__lead">Um .zip com o banco, as contas, os ajustes, o segredo das sessões e os arquivos enviados. Os vetores não entram: depois de restaurar, o Nexo reindexa sozinho.</p>
          <button className="primary-button" onClick={backup} disabled={!!busy}><Icon name="download" size={16} />{busy === "backup" ? "Gerando o arquivo…" : "Baixar backup"}</button>
          <div className="ops-cli">
            <span>Pela linha de comando, com o servidor parado para restaurar:</span>
            <code>python -m nexo backup --saida nexo.zip</code>
            <code>python -m nexo restaurar nexo.zip --substituir</code>
          </div>
        </section>
        <section className="panel">
          <h2>Conversas antigas</h2>
          <p className="panel__lead">Apaga as conversas não fixadas sem atividade há mais tempo que o informado. {status?.operation?.retention_days ? `A retenção automática está em ${status.operation.retention_days} dias.` : "A retenção automática está desligada; ligue em Ajustes."}</p>
          {confirm === "purge" ? (
            <div className="panel__actions">
              <span className="doc__confirm">Apagar as conversas com mais de {days} dias?</span>
              <button className="danger-button small" onClick={() => run("purge_conversations", Number(days))}>Apagar</button>
              <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
            </div>
          ) : (
            <form className="inline-form ops-purge" onSubmit={(e) => { e.preventDefault(); setConfirm("purge"); }}>
              <span className="muted">Mais de</span>
              <input type="number" min={1} max={3650} value={days} onChange={(e) => setDays(e.target.value)} aria-label="Dias sem atividade" className="ops-days" />
              <span className="muted">dias</span>
              <button className="ghost-button small" type="submit" disabled={!Number(days) || !!busy}><Icon name="trash" size={15} />Apagar antigas</button>
            </form>
          )}
        </section>
      </div>
      <div className="box">
        <section className="panel">
          <h2>Acervo e banco</h2>
          <p className="panel__lead">{plural(failed, "documento com falha", "documentos com falha")} e {plural(outdated, "desatualizado", "desatualizados")} agora. As reindexações entram na fila e seguem enquanto você usa o Nexo.</p>
          <ul className="ops-actions">
            {MAINTENANCE.map((m) => (
              <li key={m.action}>
                <span className="ops-actions__icon"><Icon name={m.icon} size={16} /></span>
                <div><strong>{m.title}</strong><p>{m.text}</p></div>
                {confirm === m.action ? (
                  <span className="panel__actions">
                    <span className="doc__confirm">{m.confirm}</span>
                    <button className="danger-button small" onClick={() => run(m.action)}>Confirmar</button>
                    <button className="ghost-button small" onClick={() => setConfirm(null)}>Cancelar</button>
                  </span>
                ) : (
                  <button className="ghost-button small" disabled={!!busy || (m.action === "reindex_failed" && !failed) || (m.action === "reindex_outdated" && !outdated)}
                    onClick={() => (m.confirm ? setConfirm(m.action) : run(m.action))}>
                    {busy === m.action ? "Rodando…" : "Rodar"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

const ACTION_GROUPS: { prefix: string; label: string }[] = [
  { prefix: "", label: "Todas" },
  { prefix: "auth.", label: "Entradas e senhas" },
  { prefix: "user.", label: "Contas" },
  { prefix: "base.", label: "Bases" },
  { prefix: "document.", label: "Documentos" },
  { prefix: "bot.", label: "Agentes" },
  { prefix: "key.", label: "Chaves de API" },
  { prefix: "webhook.", label: "Webhooks" },
  { prefix: "channel.", label: "Conexões do WhatsApp" },
  { prefix: "reply.", label: "Respostas prontas" },
  { prefix: "settings.", label: "Ajustes" },
  { prefix: "maintenance.", label: "Manutenção" },
  { prefix: "system.", label: "Backups" },
];

function details(raw: string | null): string {
  if (!raw) return "";
  try {
    const value = JSON.parse(raw) as unknown;
    if (Array.isArray(value)) return value.join(", ");
    if (value && typeof value === "object") {
      return Object.entries(value as Record<string, unknown>)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}`)
        .join(" · ");
    }
    return String(value);
  } catch {
    return raw;
  }
}

function ActivityPanel() {
  const toast = useToast();
  const [page, setPage] = useState<AuditPage | null>(null);
  const [actor, setActor] = useState("");
  const [prefix, setPrefix] = useState("");
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);

  async function load(offset = 0) {
    setBusy(true);
    try {
      const next = await api.audit({ actor: actor.trim().toLowerCase(), action: prefix, days, offset, limit: 50 });
      setPage((current) => (offset && current ? { ...next, items: [...current.items, ...next.items] } : next));
    } catch (e) {
      toast((e as ApiError).message, "error");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(0), actor ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [actor, prefix, days]);

  async function exportCsv() {
    try {
      await downloadAudit({ actor: actor.trim().toLowerCase(), action: prefix, days });
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  return (
    <div className="box">
      <section className="panel">
        <div className="ops-head">
          <div>
            <h2>Registro de atividades</h2>
            <p className="panel__lead">Quem entrou, quem criou, alterou ou excluiu bases, agentes, documentos, contas, chaves e conexões, e quem mexeu nos ajustes. Use para auditoria e para entender mudanças no comportamento dos agentes.</p>
          </div>
          <button className="ghost-button small" onClick={exportCsv} disabled={!page?.total}><Icon name="download" size={15} />Exportar CSV</button>
        </div>
        <div className="toolbar ops-toolbar">
          <input className="toolbar__search" value={actor} onChange={(e) => setActor(e.target.value)} placeholder="Conta (usuário exato)" aria-label="Filtrar por conta" />
          <label className="select"><span>Tipo</span>
            <select value={prefix} onChange={(e) => setPrefix(e.target.value)}>
              {ACTION_GROUPS.map((g) => <option key={g.prefix} value={g.prefix}>{g.label}</option>)}
            </select>
          </label>
          <label className="select"><span>Período</span>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={1}>Últimas 24 horas</option>
              <option value={7}>7 dias</option>
              <option value={30}>30 dias</option>
              <option value={90}>90 dias</option>
              <option value={0}>Tudo</option>
            </select>
          </label>
        </div>
        {page && page.items.length === 0 && <p className="panel__lead">Nenhuma atividade com esses filtros.</p>}
        {page && page.items.length > 0 && (
          <div className="table-wrap">
            <table className="table ops-audit">
              <thead><tr><th>Quando</th><th>Conta</th><th>O que fez</th><th>Detalhes</th><th>Origem</th></tr></thead>
              <tbody>
                {page.items.map((i) => (
                  <tr key={i.id} className={i.action === "auth.login_failed" ? "is-alert" : ""}>
                    <td className="ops-when">{formatDateTime(i.created_at)}</td>
                    <td><code>{i.actor}</code></td>
                    <td>{i.label}</td>
                    <td className="ops-detail" title={i.detail ?? undefined}>{details(i.detail) || (i.target_id ? <code>{i.target_id}</code> : "—")}</td>
                    <td className="muted">{i.ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {page && page.items.length < page.total && (
          <div className="panel__actions">
            <button className="ghost-button small" onClick={() => load(page.items.length)} disabled={busy}>
              {busy ? "Carregando…" : `Carregar mais (${(page.total - page.items.length).toLocaleString("pt-BR")} restantes)`}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export function SystemPage() {
  const { user, signIn, updateUser } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const admin = user?.role === "admin";
  const tab = (admin ? TABS.find((t) => t.id === params.get("aba"))?.id : null) ?? "geral";

  const loadStatus = () => api.status().then(setStatus).catch((e: ApiError) => setError(e.message));
  useEffect(() => { void loadStatus(); }, [tab]);

  function setTab(next: Tab) {
    setParams(next === "geral" ? {} : { aba: next }, { replace: true });
  }

  async function reindexOutdated() {
    try {
      const out = await api.maintenance("reindex_outdated");
      toast(out.message);
      void loadStatus();
    } catch (e) {
      toast((e as ApiError).message, "error");
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    setSaved("");
    if (form.next !== form.confirm) {
      setFieldErrors({ confirm: "As senhas não conferem." });
      return;
    }
    setBusy(true);
    try {
      signIn(await api.changePassword(form.current, form.next));
      setForm({ current: "", next: "", confirm: "" });
      setSaved("Senha alterada. As outras sessões abertas com a sua conta foram encerradas.");
    } catch (err) {
      const apiError = err as ApiError;
      const fields = apiError.fields ?? {};
      setFieldErrors({
        current: fields.current_password ?? "",
        next: fields.password ?? fields.new_password ?? "",
        ...(Object.keys(fields).length ? {} : { form: apiError.message }),
      });
    } finally {
      setBusy(false);
    }
  }

  async function saveName(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || name.trim() === user?.name) {
      setRenaming(false);
      return;
    }
    try {
      updateUser(await api.updateMe(name.trim()));
      toast("Nome atualizado.");
      setRenaming(false);
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  async function revoke() {
    try {
      signIn(await api.revokeSessions());
      toast("Pronto. Só esta sessão continua aberta.");
    } catch (err) {
      toast((err as ApiError).message, "error");
    }
  }

  const p = status?.providers;
  const op = status?.operation;
  const rows: [string, string][] = p ? [
    ["Modelo de linguagem", p.llm],
    ["Embeddings", p.embedding],
    ["Reranking", p.reranker],
    ["Banco vetorial", `${p.vector_store}, coleção ${p.collection}`],
    ["Banco relacional", status!.database],
    ["Tamanho do trecho", `${p.chunk_size} tokens, sobreposição de ${p.chunk_overlap}`],
    ["Busca", `${p.top_k} candidatos, ${p.top_n} vão para o modelo`],
    ["Cortes de relevância", `similaridade mínima ${p.min_similarity}, reranking mínimo ${p.min_rerank_score}`],
    ["Verificação de fidelidade", p.verify_answers ? "Ligada" : "Desligada"],
    ["Cadastro de contas", status!.registration ? "Aberto" : "Fechado"],
    ...(op ? [
      ["Limite de perguntas", op.rate_limit ? `${op.rate_limit} por minuto por conta` : "Sem limite"],
      ["Retenção de conversas", op.retention_days ? `${op.retention_days} dias` : "Para sempre"],
      ["Sessão", `${op.token_hours} horas`],
    ] as [string, string][] : []),
  ] : [];

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Configuração</span>
          <h1>Sistema e conta</h1>
          <p className="page__lead">{admin ? "Configuração ativa, ajustes, diagnóstico, manutenção, registro de atividades e contas." : "Configuração ativa do servidor e os dados da sua conta."}</p>
        </div>
        {status && <span className="version">Versão {status.version}</span>}
      </header>
      {error && <p className="alert" role="alert">{error}</p>}

      {admin && (
        <div className="segmented ops-tabs" role="tablist" aria-label="Seções do sistema">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
      )}

      {tab === "geral" && (
        <>
          <div className="system box">
            <section className="panel">
              <h2>Pipeline de respostas</h2>
              <p className="panel__lead">
                {admin
                  ? <>Modelo, busca, cortes, tamanho do trecho, cadastro e limites mudam na aba <button className="link-button" onClick={() => setTab("ajustes")}>Ajustes</button>, sem reiniciar. Provedores e bancos ficam no <code>.env</code>.</>
                  : <>Para mudar qualquer item, peça a um administrador. O passo a passo está no <code>Manual-Nexo.pdf</code>.</>}
                {op?.overrides.length ? ` ${plural(op.overrides.length, "item ajustado", "itens ajustados")} pela tela.` : ""}
              </p>
              <dl className="config">
                {rows.map(([k, v]) => (
                  <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
                ))}
              </dl>
            </section>

            <section className="panel panel--lid">
              <h2>Acervo</h2>
              {status && (
                <div className="figures">
                  <div><strong>{status.documents.by_status.READY ?? 0}</strong><span>documentos prontos</span></div>
                  <div><strong>{status.documents.chunks.toLocaleString("pt-BR")}</strong><span>trechos indexados</span></div>
                  <div><strong>{(status.documents.by_status.PENDING ?? 0) + (status.documents.by_status.PROCESSING ?? 0)}</strong><span>na fila</span></div>
                  <div><strong>{status.documents.by_status.FAILED ?? 0}</strong><span>com falha</span></div>
                  {!!status.documents.outdated && <div><strong>{status.documents.outdated}</strong><span>com índice desatualizado</span></div>}
                  {status.users !== null && <div><strong>{status.users}</strong><span>contas cadastradas</span></div>}
                  {status.integrations && <div><strong>{status.integrations.api_keys}</strong><span>suas chaves de API</span></div>}
                  {status.integrations?.webhooks != null && <div><strong>{status.integrations.webhooks}</strong><span>webhooks</span></div>}
                </div>
              )}
            </section>

            <section className="panel">
              <h2>Sua conta</h2>
              <dl className="config">
                <div><dt>Nome</dt><dd>
                  {renaming ? (
                    <form className="inline-form" onSubmit={saveName}>
                      <input aria-label="Seu nome" value={name} autoFocus maxLength={80} onChange={(e) => setName(e.target.value)}
                        onKeyDown={(e) => e.key === "Escape" && setRenaming(false)} />
                      <button className="primary-button small" type="submit">Salvar</button>
                    </form>
                  ) : (
                    <>
                      {user?.name}{" "}
                      <button className="link-button" type="button" onClick={() => { setName(user?.name ?? ""); setRenaming(true); }}>Editar</button>
                    </>
                  )}
                </dd></div>
                <div><dt>Usuário</dt><dd>{user?.username}</dd></div>
                <div><dt>Perfil</dt><dd>{user?.role === "admin" ? "Administrador" : "Usuário"}</dd></div>
                <div><dt>Conta criada em</dt><dd>{formatDateTime(user?.created_at ?? null)}</dd></div>
                <div><dt>Tutorial</dt><dd>{user?.tutorial_done_at ? `Visto em ${formatDateTime(user.tutorial_done_at)}` : "Ainda não visto"}</dd></div>
                <div><dt>Senha trocada em</dt><dd>{user?.password_changed_at ? formatDateTime(user.password_changed_at) : "Nunca trocada"}</dd></div>
              </dl>
              <div className="panel__actions">
                <button className="ghost-button" type="button" onClick={openTutorial}>
                  <Icon name="help" size={16} />Rever o tutorial
                </button>
                <button className="ghost-button" type="button" onClick={revoke}
                  title="Encerra as sessões abertas em outros navegadores e aparelhos">
                  <Icon name="logout" size={16} />Sair dos outros dispositivos
                </button>
              </div>
              <form className="password-form" onSubmit={changePassword} noValidate>
                <h3>Trocar senha</h3>
                <Field label="Senha atual" name="current" type="password" autoComplete="current-password" value={form.current}
                  onChange={(e) => setForm({ ...form, current: e.target.value })} error={fieldErrors.current} />
                <Field label="Nova senha" name="next" type="password" autoComplete="new-password" value={form.next}
                  onChange={(e) => setForm({ ...form, next: e.target.value })} error={fieldErrors.next}
                  hint="De 8 a 72 caracteres, com letras e números." />
                <Field label="Repita a nova senha" name="confirm" type="password" autoComplete="new-password" value={form.confirm}
                  onChange={(e) => setForm({ ...form, confirm: e.target.value })} error={fieldErrors.confirm} />
                {fieldErrors.form && <p className="alert" role="alert">{fieldErrors.form}</p>}
                {saved && <p className="alert alert--ok" role="status">{saved}</p>}
                <button className="primary-button" type="submit" disabled={busy || !form.current || !form.next}>
                  {busy ? "Salvando…" : "Trocar senha"}
                </button>
              </form>
            </section>
          </div>
          {admin && (
            <p className="ops-more">
              Precisa conferir se está tudo certo? Rode o <button className="link-button" onClick={() => setTab("diagnostico")}>diagnóstico</button>, baixe um <button className="link-button" onClick={() => setTab("manutencao")}>backup</button> ou veja o <a href="/api/docs" target="_blank" rel="noreferrer">guia interativo da API</a>.
            </p>
          )}
        </>
      )}
      {tab === "ajustes" && <SettingsPanel onReindex={reindexOutdated} />}
      {tab === "diagnostico" && <DiagnosticsPanel />}
      {tab === "manutencao" && <MaintenancePanel status={status} onDone={loadStatus} />}
      {tab === "atividades" && <ActivityPanel />}
      {tab === "contas" && user && <Users me={user.username} />}
    </div>
  );
}
