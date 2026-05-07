import { FormEvent, useState } from "react";

import { login } from "../lib/api";

export function LoginPage() {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await login(email, password);
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    }
  }

  return (
    <div className="auth-shell">
      <form className="panel auth-panel" onSubmit={handleSubmit}>
        <h1>Вход в XAI Report Builder</h1>
        <p>Web-first MVP для проверяемой отчетности и XAI-объяснений.</p>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
        </label>
        <label>
          Пароль
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
        </label>
        {error ? <div className="error-box">{error}</div> : null}
        <button type="submit">Войти</button>
      </form>
    </div>
  );
}
