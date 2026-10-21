import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, type SystemStatus } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { formatDateTime } from "../format";

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
        <div>
          <h1>Sistema e conta</h1>
          <p className="page__lead">Configuração ativa do servidor e os dados da sua conta.</p>
        </div>
        {status && <span className="version">Versão {status.version}</span>}
      </header>
      {error && <p className="alert" role="alert">{error}</p>}

      <div className="system">
        <section className="panel">
          <h2>Pipeline de respostas</h2>
          <p className="panel__lead">Para mudar qualquer item, edite o arquivo <code>.env</code> e reinicie o servidor. O passo a passo está no <code>Manual-Nexo.pdf</code>.</p>
          <dl className="config">
            {rows.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </section>

        <section className="panel">
          <h2>Acervo</h2>
          {status && (
            <div className="figures">
              <div><strong>{status.documents.by_status.READY ?? 0}</strong><span>documentos prontos</span></div>
              <div><strong>{status.documents.chunks.toLocaleString("pt-BR")}</strong><span>trechos indexados</span></div>
              <div><strong>{(status.documents.by_status.PENDING ?? 0) + (status.documents.by_status.PROCESSING ?? 0)}</strong><span>na fila</span></div>
              <div><strong>{status.documents.by_status.FAILED ?? 0}</strong><span>com falha</span></div>
              {status.users !== null && <div><strong>{status.users}</strong><span>contas cadastradas</span></div>}
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
            {saved && <p className="alert alert--ok" role="status">{saved}</p>}
            <button className="primary-button" type="submit" disabled={busy || !form.current || !form.next}>
              {busy ? "Salvando…" : "Trocar senha"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
