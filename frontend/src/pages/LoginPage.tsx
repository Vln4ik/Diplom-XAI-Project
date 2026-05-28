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
      <section className="auth-showcase">
        <div className="auth-brand-ribbon">
          <span className="brand-mark">EX.AI</span>
          <span className="eyebrow">Платформа EvidenceXAI</span>
        </div>
        <h1>EvidenceXAI</h1>
        <p className="auth-lead">
          Веб-платформа для объяснимой доказательно-ориентированной отчётности, где требования, доказательства, риски и
          XAI-объяснения собираются в один рабочий контур.
        </p>
        <div className="auth-feature-grid">
          <article className="auth-feature-card">
            <strong>Сценарий, основанный на evidence</strong>
            <p>Документы, матрица, XAI и отчёт связаны в один прозрачный сценарий.</p>
          </article>
          <article className="auth-feature-card">
            <strong>Объяснимые решения</strong>
            <p>Каждое значимое решение можно объяснить через требование, evidence, confidence и risk.</p>
          </article>
          <article className="auth-feature-card">
            <strong>Проверка человеком</strong>
            <p>Специалист сохраняет контроль над согласованием, корректировкой и финальным выпуском пакета.</p>
          </article>
        </div>
      </section>
      <form className="panel auth-panel" onSubmit={handleSubmit}>
        <p className="eyebrow">Вход в рабочее пространство</p>
        <h2>Продолжить в EvidenceXAI</h2>
        <p className="helper-text">Используй тестовую учётную запись или свой локальный контур, чтобы открыть рабочее пространство EX.AI.</p>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
        </label>
        <label>
          Пароль
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
        </label>
        {error ? <div className="error-box">{error}</div> : null}
        <button type="submit" className="action-button action-primary">
          Войти в EX.AI
        </button>
      </form>
    </div>
  );
}
