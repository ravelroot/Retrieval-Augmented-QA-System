import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, type SystemStatus, type User } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { Icon } from "../components/Icon";
import { openTutorial } from "../components/Shell";
import { useToast } from "../components/Toast";
import { formatDateTime } from "../format";

function Users({ me }: { me: string }) {
  const toast = useToast();
  const [users, setUsers] = useState<User[] | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const load = () => api.users().then(setUsers).catch((e: ApiError) => toast(e.message, "error"));
  useEffect(() => { void load(); }, []);

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
        <p className="panel__lead">Promova quem administra o acervo e exclua contas que não usam mais o Nexo. Excluir uma conta apaga também as conversas e as chaves de API dela. Senha esquecida: <code>python scripts/redefinir_senha.py usuario</code>.</p>
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
                    {u.username === me ? null : confirm === u.username ? (
                      <>
                        <button className="danger-button small" onClick={() => run(() => api.deleteUser(u.username), "Conta excluída.")}>Excluir</button>
                        <button className="ghost-button small" onClick={() => setConfirm(null)}>Manter</button>
                      </>
                    ) : (
                      <button className="link-button link-button--danger" onClick={() => setConfirm(u.username)}>Excluir</button>
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
  const { user } = useAuth();
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
      await api.changePassword(form.current, form.next);
      setForm({ current: "", next: "", confirm: "" });
      setSaved("Senha alterada.");
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
            <div><dt>Nome</dt><dd>{user?.name}</dd></div>
            <div><dt>Usuário</dt><dd>{user?.username}</dd></div>
            <div><dt>Perfil</dt><dd>{user?.role === "admin" ? "Administrador" : "Usuário"}</dd></div>
            <div><dt>Conta criada em</dt><dd>{formatDateTime(user?.created_at ?? null)}</dd></div>
            <div><dt>Tutorial</dt><dd>{user?.tutorial_done_at ? `Visto em ${formatDateTime(user.tutorial_done_at)}` : "Ainda não visto"}</dd></div>
          </dl>
          <button className="ghost-button tutorial-again" type="button" onClick={openTutorial}>
            <Icon name="help" size={16} />Rever o tutorial
          </button>
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
