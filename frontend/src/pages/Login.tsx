import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, api, type AuthOptions } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/Field";
import { LogoMark } from "../components/Logo";

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
        <LogoMark size={220} className="login__mark" />
        <div>
          <h1>Nexo</h1>
          <p>Pergunte aos seus manuais técnicos e livros. Cada resposta vem dos PDFs enviados, com a página de onde saiu.</p>
        </div>
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
          <h2>{mode === "login" ? "Entre na sua conta" : "Crie sua conta"}</h2>
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
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "Aguarde…" : mode === "login" ? "Entrar" : "Criar conta e entrar"}
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
