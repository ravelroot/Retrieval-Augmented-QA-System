import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, api, type AuthOptions } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { Brand } from "../components/Logo";

type Mode = "login" | "register";

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("login");
  const [options, setOptions] = useState<AuthOptions | null>(null);
  const [form, setForm] = useState({ name: "", username: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.options().then(setOptions).catch((e: ApiError) => setMessage(e.message));
  }, []);

  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  function switchMode(next: Mode) {
    setMode(next);
    setErrors({});
    setMessage("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    setMessage("");
    if (mode === "register" && form.password !== form.confirm) {
      setErrors({ confirm: "As senhas não conferem." });
      return;
    }
    setBusy(true);
    try {
      const session = mode === "login"
        ? await api.login(form.username, form.password)
        : await api.register(form.name, form.username, form.password);
      signIn(session);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/entrar" ? from : "/conversas", { replace: true });
    } catch (err) {
      const error = err as ApiError;
      if (Object.keys(error.fields ?? {}).length) setErrors(error.fields);
      else setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login__brand">
        <Brand />
        <div className="login__pitch">
          <h1>Pergunte aos seus manuais. A resposta vem com a página.</h1>
          <p>O Nexo lê os PDFs que você envia e responde só com o que está neles. Se a informação não estiver lá, ele diz que não encontrou.</p>
        </div>
        <figure className="specimen" aria-label="Exemplo de resposta com fonte">
          <p className="specimen__q">De quanto em quanto tempo lubrificar os rolamentos?</p>
          <p className="specimen__a">A cada 2.000 horas, com graxa de lítio grau NLGI 2.<span className="specimen__cite">1</span></p>
          <div className="specimen__page">
            <span className="specimen__tab">p. 2</span>
            <p>
              <span className="specimen__doc">Guia de Manutenção da Bomba BC-40</span>
              2. Lubrificação. <mark>Os rolamentos devem ser lubrificados a cada 2.000 horas de operação com graxa à base de lítio, grau NLGI 2.</mark> Aplique 15 gramas de graxa em cada rolamento.
            </p>
          </div>
        </figure>
        <p className="login__legal">Copyright (©) 2026 Erik Pimenta. Licença MIT.</p>
      </section>
      <section className="login__panel">
        <form className="login__form" onSubmit={submit} noValidate>
          <div className="segmented" role="tablist" aria-label="Acesso">
            <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => switchMode("login")}>
              Entrar
            </button>
            {options?.registration !== false && (
              <button type="button" role="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>
                Criar conta
              </button>
            )}
          </div>
          <div className="login__titles">
            <h2>{mode === "login" ? "Entrar" : "Criar conta"}</h2>
            <p>{mode === "login" ? "Use o usuário e a senha da sua conta." : "Escolha um usuário e uma senha para acessar o Nexo."}</p>
          </div>
          {mode === "register" && (
            <Field label="Nome" name="name" autoComplete="name" value={form.name} onChange={update("name")}
              error={errors.name} required />
          )}
          <Field label="Usuário" name="username" autoComplete="username" autoCapitalize="none" value={form.username}
            onChange={update("username")} error={errors.username} required
            hint={mode === "register" ? "De 3 a 32 letras minúsculas, números, ponto, hífen ou sublinhado." : undefined} />
          <Field label="Senha" name="password" type="password" value={form.password} onChange={update("password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"} error={errors.password} required
            hint={mode === "register" ? "De 8 a 72 caracteres, com letras e números." : undefined} />
          {mode === "register" && (
            <Field label="Repita a senha" name="confirm" type="password" autoComplete="new-password"
              value={form.confirm} onChange={update("confirm")} error={errors.confirm} required />
          )}
          {message && <p className="alert" role="alert">{message}</p>}
          <button className="button button--primary login__submit" type="submit" disabled={busy}>
            {busy ? "Aguarde…" : mode === "login" ? "Entrar no Nexo" : "Criar conta e entrar"}
          </button>
          {mode === "login" && options?.default_admin && (
            <div className="note">
              <strong>Primeiro acesso</strong>
              <p>Use o login pré-definido <code>admin</code> com a senha <code>Nexo@2026</code> e troque a senha em Sistema e conta.</p>
            </div>
          )}
          {mode === "register" && (
            <p className="login__aside">Sua conta fica salva no arquivo <code>data/usuarios.json</code> do servidor, com a senha protegida por bcrypt.</p>
          )}
        </form>
      </section>
    </div>
  );
}
