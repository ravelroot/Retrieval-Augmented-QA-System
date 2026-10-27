import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, type SystemStatus, type User } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
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
    <section className="sheet">
      <h2>Contas</h2>
      <p className="sheet__lead">Promova quem administra o acervo e remova contas que não usam mais o Nexo. Senhas esquecidas: <code>python scripts/redefinir_senha.py usuario</code>.</p>
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
                    <button className="button button--danger button--small" onClick={() => run(() => api.deleteUser(u.username), "Conta excluída.")}>Excluir</button>
                    <button className="button button--small" onClick={() => setConfirm(null)}>Manter</button>
                  </>
                ) : (
                  <button className="text-button text-button--danger" onClick={() => setConfirm(u.username)}>Excluir</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function SystemPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api.status().then(setStatus).catch((e: ApiError) => setError(e.message));
  }, []);

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    if (form.next !== form.confirm) {
      setFieldErrors({ confirm: "As senhas não conferem." });
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(form.current, form.next);
      setForm({ current: "", next: "", confirm: "" });
      toast("Senha alterada.");
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
  const flow = p ? [
    { step: "Pergunta reescrita com o histórico", value: "Resolve “isso”, “o passo seguinte”" },
    { step: "Busca vetorial", value: `${p.top_k} candidatos, ${p.embedding}`, detail: `${p.vector_store}, coleção ${p.collection}` },
    { step: "Corte de similaridade", value: `mínimo ${p.min_similarity}`, cut: true },
    { step: "Reranking", value: p.reranker },
    { step: "Corte do reranker", value: `mínimo ${p.min_rerank_score}, ${p.top_n} trechos seguem`, cut: true },
    { step: "Resposta com citações", value: p.llm },
    { step: "Verificação de fidelidade", value: p.verify_answers ? "Ligada" : "Desligada" },
  ] : [];

  return (
    <div className="page">
      <header className="page__head page__head--row">
        <div>
          <h1>Sistema e conta</h1>
          <p className="page__lead">Como o servidor responde, o tamanho do acervo e os dados da sua conta.</p>
        </div>
        {status && <span className="version">Versão {status.version}</span>}
      </header>
      {error && <p className="alert" role="alert">{error}</p>}

      {p && status && (
        <div className="grid-2 grid-2--system">
          <section className="sheet">
            <h2>Caminho de cada resposta</h2>
            <p className="sheet__lead">Se nenhum trecho passar em um dos cortes, o modelo nem é chamado e o Nexo diz que não encontrou. Para mudar, edite o <code>.env</code> e reinicie o servidor.</p>
            <ol className="flow">
              {flow.map((f) => (
                <li key={f.step} className={f.cut ? "flow__cut" : ""}>
                  <span className="flow__step">{f.step}</span>
                  <span className="flow__value">{f.value}</span>
                  {f.detail && <span className="flow__detail">{f.detail}</span>}
                </li>
              ))}
            </ol>
            <dl className="config">
              <div><dt>Tamanho do trecho</dt><dd>{p.chunk_size} tokens, sobreposição de {p.chunk_overlap}</dd></div>
              <div><dt>Banco relacional</dt><dd>{status.database}</dd></div>
              <div><dt>Cadastro de contas</dt><dd>{status.registration ? "Aberto" : "Fechado"}</dd></div>
            </dl>
          </section>

          <div className="stack">
            <section className="sheet">
              <h2>Acervo</h2>
              <dl className="figures">
                <div><dt>Documentos prontos</dt><dd>{status.documents.by_status.READY ?? 0}</dd></div>
                <div><dt>Trechos indexados</dt><dd>{status.documents.chunks.toLocaleString("pt-BR")}</dd></div>
                <div><dt>Na fila</dt><dd>{(status.documents.by_status.PENDING ?? 0) + (status.documents.by_status.PROCESSING ?? 0)}</dd></div>
                <div><dt>Com falha</dt><dd>{status.documents.by_status.FAILED ?? 0}</dd></div>
                {status.users !== null && <div><dt>Contas</dt><dd>{status.users}</dd></div>}
                {status.integrations && <div><dt>Suas chaves de API</dt><dd>{status.integrations.api_keys}</dd></div>}
                {status.integrations?.webhooks != null && <div><dt>Webhooks</dt><dd>{status.integrations.webhooks}</dd></div>}
              </dl>
            </section>

            <section className="sheet">
              <h2>Sua conta</h2>
              <dl className="config">
                <div><dt>Nome</dt><dd>{user?.name}</dd></div>
                <div><dt>Usuário</dt><dd>{user?.username}</dd></div>
                <div><dt>Perfil</dt><dd>{user?.role === "admin" ? "Administrador" : "Usuário"}</dd></div>
                <div><dt>Conta criada em</dt><dd>{formatDateTime(user?.created_at ?? null)}</dd></div>
              </dl>
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
                <button className="button button--primary" type="submit" disabled={busy || !form.current || !form.next}>
                  {busy ? "Salvando…" : "Trocar senha"}
                </button>
              </form>
            </section>
          </div>
        </div>
      )}

      {user?.role === "admin" && <Users me={user.username} />}
    </div>
  );
}
