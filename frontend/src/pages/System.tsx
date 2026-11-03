import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, type SystemStatus, type User } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { Icon } from "../components/Icon";
import { openTutorial } from "../components/Shell";
import { useToast } from "../components/Toast";
import { formatDateTime } from "../format";

const EMPTY_ACCOUNT = { name: "", username: "", password: "", role: "user" as User["role"] };

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
          </div>
        )}
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Nome</th><th>Usuário</th><th>Perfil</th><th>Último acesso</th><th><span className="sr-only">Ações</span></th></tr></thead>
            <tbody>
              {users.map((u) => (
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

export function SystemPage() {
  const { user, signIn, updateUser } = useAuth();
  const toast = useToast();
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.status().then(setStatus).catch((e: ApiError) => setError(e.message));
  }, []);

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
  ] : [];

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Configuração</span>
          <h1>Sistema e conta</h1>
          <p className="page__lead">Configuração ativa do servidor e os dados da sua conta.</p>
        </div>
        {status && <span className="version">Versão {status.version}</span>}
      </header>
      {error && <p className="alert" role="alert">{error}</p>}

      <div className="system box">
        <section className="panel">
          <h2>Pipeline de respostas</h2>
          <p className="panel__lead">Para mudar qualquer item, edite o arquivo <code>.env</code> e reinicie o servidor. O passo a passo está no <code>Manual-Nexo.pdf</code>.</p>
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
      {user?.role === "admin" && <Users me={user.username} />}
    </div>
  );
}
